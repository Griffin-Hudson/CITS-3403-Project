"""System tests for TuneFeed using Selenium WebDriver.

Follows the lecture pattern from Week13-Testing slides 29-30:

    self.testApp = create_app(TestConfig)
    self.app_context = self.testApp.app_context()
    self.app_context.push()
    db.create_all()
    add_test_data_to_db()

    self.server_thread = multiprocessing.Process(target=self.testApp.run)
    self.server_thread.start()

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    self.driver = webdriver.Chrome(options=options)

    # tearDown
    self.server_thread.terminate()
    self.driver.close()
    db.session.remove()
    db.drop_all()
    self.app_context.pop()

A temporary file-based SQLite database is used because multiprocessing
starts a separate OS process — an in-memory database is not shared
across process boundaries.  Chrome runs in headless mode so the tests
work in CI environments without a display server.

Run with:
    python -m unittest tests.test_selenium -v

Requirements:
    pip install selenium
    Google Chrome must be installed on the test machine.
    Selenium 4.x downloads chromedriver automatically.
"""

import multiprocessing
import os
import tempfile
import time
import unittest

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app import create_app
from app.models import db, Beat, User

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PORT = 5001
_HOST = f'http://localhost:{_PORT}'
_WAIT = 8


# ---------------------------------------------------------------------------
# Server process target — must be at module level for multiprocessing pickling
# ---------------------------------------------------------------------------

def _run_server(db_path):
    """Start the Flask dev server using a file-based SQLite database."""
    class _Cfg:
        TESTING = True
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{db_path}'
        WTF_CSRF_ENABLED = False
        SECRET_KEY = 'selenium-test-secret-key'
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        RATELIMIT_ENABLED = False

    create_app(_Cfg).run(port=_PORT, use_reloader=False, threaded=True)


# ---------------------------------------------------------------------------
# Base test class — setUp / tearDown follow the lecture pattern (slides 29-30)
# ---------------------------------------------------------------------------

class _SeleniumBase(unittest.TestCase):
    """Selenium base that mirrors the lecture setUp/tearDown structure.

    setUpClass  creates the app, seeds the DB, starts Flask via
                multiprocessing.Process, and launches headless Chrome —
                once per test class.
    setUp       clears cookies and navigates to /login before each test,
                providing the same per-test isolation the lecture shows.
    tearDownClass terminates the server process, closes the browser, and
                cleans up the temporary database — matching the lecture's
                tearDown sequence:
                    self.server_thread.terminate()
                    self.driver.close()
                    db.session.remove()
                    db.drop_all()
                    self.app_context.pop()
    """

    # Class-level attributes set by setUpClass, accessible as self.<attr>
    testApp = None
    app_context = None
    server_thread = None   # named 'server_thread' to match lecture variable name
    driver = None
    _db_fd = None
    _db_path = None
    _beat_id = None

    @classmethod
    def setUpClass(cls):
        # Temp file-based DB visible to both the test process and the server process
        cls._db_fd, cls._db_path = tempfile.mkstemp(suffix='_selenium_test.db')

        # Build the app and seed the database (lecture: add_test_data_to_db())
        class _Cfg:
            TESTING = True
            SQLALCHEMY_DATABASE_URI = f'sqlite:///{cls._db_path}'
            WTF_CSRF_ENABLED = False
            SECRET_KEY = 'selenium-test-secret-key'
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            RATELIMIT_ENABLED = False

        cls.testApp = create_app(_Cfg)
        cls.app_context = cls.testApp.app_context()
        cls.app_context.push()
        db.create_all()

        u = User(username='seluser', email='seluser@test.com')
        u.set_password('SelPass1!')
        db.session.add(u)
        db.session.flush()
        b = Beat(
            title='Selenium Test Beat',
            audio_url='/static/audio/demo.mp3',
            producer_id=u.id,
            price=0.0,
        )
        db.session.add(b)
        db.session.commit()
        cls._beat_id = b.id

        # Start Flask in a separate process — lecture pattern (slide 29):
        #   self.server_thread = multiprocessing.Process(target=self.testApp.run)
        #   self.server_thread.start()
        cls.server_thread = multiprocessing.Process(
            target=_run_server,
            args=(cls._db_path,),
            daemon=True,
        )
        cls.server_thread.start()
        time.sleep(1.5)  # allow Werkzeug to bind and begin serving

        # Launch Chrome in headless mode — lecture pattern (slide 30):
        #   options = webdriver.ChromeOptions()
        #   options.add_argument("--headless=new")
        #   self.driver = webdriver.Chrome(options=options)
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1280,800')
        cls.driver = webdriver.Chrome(options=options)
        cls.driver.implicitly_wait(2)

    def setUp(self):
        """Clear cookies and navigate to /login before each test for isolation."""
        self.driver.delete_all_cookies()
        self.driver.get(_HOST + '/login')
        WebDriverWait(self.driver, _WAIT).until(
            EC.presence_of_element_located((By.ID, 'email'))
        )

    @classmethod
    def tearDownClass(cls):
        """Terminate the server and close the browser — lecture pattern (slide 30):
            self.server_thread.terminate()
            self.driver.close()
            db.session.remove()
            db.drop_all()
            self.app_context.pop()
        """
        if cls.server_thread and cls.server_thread.is_alive():
            cls.server_thread.terminate()
            cls.server_thread.join(timeout=5)
        if cls.driver:
            cls.driver.close()
        db.session.remove()
        db.drop_all()
        if cls.app_context:
            cls.app_context.pop()
        if cls._db_fd is not None:
            try:
                os.close(cls._db_fd)
            except OSError:
                pass
        if cls._db_path and os.path.exists(cls._db_path):
            try:
                os.unlink(cls._db_path)
            except OSError:
                pass

    def _login(self, email='seluser@test.com', password='SelPass1!'):
        """Fill and submit the login form, then wait for the redirect."""
        self.driver.get(_HOST + '/login')
        wait = WebDriverWait(self.driver, _WAIT)
        wait.until(EC.presence_of_element_located((By.ID, 'email'))).clear()
        self.driver.find_element(By.ID, 'email').send_keys(email)
        self.driver.find_element(By.ID, 'password').send_keys(password)
        self.driver.find_element(By.ID, 'login-submit').click()
        wait.until(EC.url_changes(_HOST + '/login'))

    def _logout(self):
        """Submit the logout form and wait for the redirect to /login."""
        signout = WebDriverWait(self.driver, _WAIT).until(
            EC.presence_of_element_located((By.ID, 'nav-signout'))
        )
        self.driver.execute_script("arguments[0].click();", signout)
        WebDriverWait(self.driver, _WAIT).until(EC.url_contains('/login'))


# ---------------------------------------------------------------------------
# Test class 1 — Navigation: buttons go to the correct pages
# ---------------------------------------------------------------------------

class TestNavigationButtons(_SeleniumBase):
    """Verify every navigation link and button reaches the expected page."""

    def test_brand_logo_navigates_to_discover(self):
        """Clicking the TuneFeed brand logo must open /discover."""
        wait = WebDriverWait(self.driver, _WAIT)
        wait.until(EC.presence_of_element_located((By.ID, 'nav-brand'))).click()
        wait.until(EC.url_contains('/discover'))
        self.assertIn(
            '/discover', self.driver.current_url,
            f'Brand logo should link to /discover; got {self.driver.current_url}',
        )

    def test_listen_nav_link_navigates_to_feed(self):
        """The Listen nav link must open /feed."""
        wait = WebDriverWait(self.driver, _WAIT)
        wait.until(EC.presence_of_element_located((By.ID, 'nav-listen'))).click()
        wait.until(EC.url_contains('/feed'))
        self.assertIn(
            '/feed', self.driver.current_url,
            f'Listen nav link should open /feed; got {self.driver.current_url}',
        )

    def test_discover_nav_link_navigates_to_discover(self):
        """The Discover nav link must open /discover."""
        wait = WebDriverWait(self.driver, _WAIT)
        wait.until(EC.presence_of_element_located((By.ID, 'nav-discover'))).click()
        wait.until(EC.url_contains('/discover'))
        self.assertIn(
            '/discover', self.driver.current_url,
            f'Discover nav link should open /discover; got {self.driver.current_url}',
        )

    def test_signin_nav_link_has_correct_href(self):
        """The Sign In nav link must point to /login."""
        wait = WebDriverWait(self.driver, _WAIT)
        link = wait.until(EC.presence_of_element_located((By.ID, 'nav-signin')))
        self.assertIn(
            '/login', link.get_attribute('href'),
            'Sign In nav link must point to /login',
        )

    def test_join_nav_button_has_correct_href(self):
        """The Join nav button must point to /register."""
        wait = WebDriverWait(self.driver, _WAIT)
        link = wait.until(EC.presence_of_element_located((By.ID, 'nav-join')))
        self.assertIn(
            '/register', link.get_attribute('href'),
            'Join nav button must point to /register',
        )

    def test_login_page_join_link_navigates_to_register(self):
        """The 'Join TuneFeed' link on the login page must open /register."""
        wait = WebDriverWait(self.driver, _WAIT)
        links = self.driver.find_elements(By.CSS_SELECTOR, 'a.auth-switch-link')
        register_links = [l for l in links if '/register' in (l.get_attribute('href') or '')]
        self.assertTrue(
            register_links,
            'Login page must contain an auth-switch link pointing to /register',
        )
        link = register_links[0]
        self.driver.execute_script("arguments[0].click();", link)
        wait.until(EC.url_contains('/register'))
        self.assertIn('/register', self.driver.current_url)

    def test_register_page_signin_link_navigates_to_login(self):
        """The 'Sign In' link on the register page must return to /login."""
        self.driver.get(_HOST + '/register')
        wait = WebDriverWait(self.driver, _WAIT)
        link = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a.auth-switch-link')))
        self.assertIn(
            '/login', link.get_attribute('href'),
            'Register page must contain an auth-switch link pointing to /login',
        )
        # The register form overflows the 800 px headless viewport; the auth-page
        # flex container's empty bottom portion sits above the link in z-order and
        # intercepts a synthetic click.  JS click fires directly on the DOM node,
        # bypassing Chrome's element-at-point check while still triggering navigation.
        self.driver.execute_script("arguments[0].click();", link)
        wait.until(EC.url_contains('/login'))
        self.assertIn('/login', self.driver.current_url)


# ---------------------------------------------------------------------------
# Test class 2 — Login and logout user story
# ---------------------------------------------------------------------------

class TestLoginFlow(_SeleniumBase):
    """End-to-end authentication flow: login, session persistence, logout."""

    def test_valid_credentials_redirect_off_login(self):
        """Submitting correct credentials must navigate away from /login."""
        self._login()
        self.assertNotIn(
            '/login', self.driver.current_url,
            f'Successful login must redirect away from /login; still at {self.driver.current_url}',
        )
        self._logout()

    def test_invalid_password_stays_on_login(self):
        """Submitting a wrong password must keep the user on /login."""
        self.driver.get(_HOST + '/login')
        wait = WebDriverWait(self.driver, _WAIT)
        wait.until(EC.presence_of_element_located((By.ID, 'email'))).send_keys('seluser@test.com')
        self.driver.find_element(By.ID, 'password').send_keys('WRONG_PASSWORD_99!')
        self.driver.find_element(By.ID, 'login-submit').click()
        time.sleep(0.8)
        self.assertIn(
            '/login', self.driver.current_url,
            'A wrong password must not redirect away from /login',
        )

    def test_logout_redirects_to_login(self):
        """After logging out the user must land on /login."""
        self._login()
        self._logout()
        self.assertIn(
            '/login', self.driver.current_url,
            f'Logout must redirect to /login; got {self.driver.current_url}',
        )

    def test_authenticated_nav_exposes_signout_link(self):
        """After login the navigation must contain a Sign Out control."""
        self._login()
        wait = WebDriverWait(self.driver, _WAIT)
        signout = wait.until(EC.presence_of_element_located((By.ID, 'nav-signout')))
        self.assertEqual(
            'button', signout.tag_name,
            'Sign Out control must be a submit button in a POST form',
        )
        form = signout.find_element(By.XPATH, './ancestor::form[1]')
        self.assertIn(
            '/logout', form.get_attribute('action'),
            'Sign Out form must post to /logout',
        )
        self._logout()

    def test_unauthenticated_nav_shows_signin_link(self):
        """When not logged in the navigation must show the Sign In link."""
        wait = WebDriverWait(self.driver, _WAIT)
        signin = wait.until(EC.presence_of_element_located((By.ID, 'nav-signin')))
        self.assertTrue(
            signin.is_displayed(),
            'Sign In nav link must be visible to anonymous visitors',
        )


# ---------------------------------------------------------------------------
# Test class 3 — Public pages render without errors
# ---------------------------------------------------------------------------

class TestPublicPageContent(_SeleniumBase):
    """Verify all public-facing pages load and display expected content."""

    def test_login_page_has_email_and_password_fields(self):
        """The login page must render email and password inputs."""
        wait = WebDriverWait(self.driver, _WAIT)
        for field_id in ('email', 'password'):
            elem = wait.until(EC.visibility_of_element_located((By.ID, field_id)))
            self.assertTrue(
                elem.is_displayed(),
                f'Login page must display the #{field_id} field',
            )

    def test_register_page_has_all_form_fields(self):
        """The register page must render username, email, password, and confirm fields."""
        self.driver.get(_HOST + '/register')
        wait = WebDriverWait(self.driver, _WAIT)
        for field_id in ('username', 'email', 'password', 'confirm_password'):
            elem = wait.until(EC.visibility_of_element_located((By.ID, field_id)))
            self.assertTrue(
                elem.is_displayed(),
                f'Register page must display the #{field_id} field',
            )

    def test_discover_page_title_contains_discover(self):
        """Navigating to /discover must load a page with 'Discover' in the title."""
        self.driver.get(_HOST + '/discover')
        wait = WebDriverWait(self.driver, _WAIT)
        wait.until(EC.title_contains('Discover'))
        self.assertIn(
            'Discover', self.driver.title,
            f'Discover page title should contain "Discover"; got "{self.driver.title}"',
        )

    def test_feed_page_loads_without_error(self):
        """Navigating to /feed must load a page with TuneFeed in the title."""
        self.driver.get(_HOST + '/feed')
        wait = WebDriverWait(self.driver, _WAIT)
        wait.until(EC.title_contains('TuneFeed'))
        self.assertIn('TuneFeed', self.driver.title)

    def test_search_page_loads_without_error(self):
        """Navigating to /search must load a page with TuneFeed in the title."""
        self.driver.get(_HOST + '/search')
        wait = WebDriverWait(self.driver, _WAIT)
        wait.until(EC.title_contains('TuneFeed'))
        self.assertIn('TuneFeed', self.driver.title)

    def test_beat_detail_page_loads(self):
        """A beat detail page must load without a 404 for a seeded beat."""
        self.driver.get(_HOST + f'/beats/{self._beat_id}')
        wait = WebDriverWait(self.driver, _WAIT)
        wait.until(EC.title_contains('TuneFeed'))
        self.assertNotIn(
            '404', self.driver.title,
            'Beat detail page must not return 404 for a seeded beat',
        )

    def test_beat_detail_page_shows_seeded_title(self):
        """The beat detail page must render the seeded beat title from the database.

        Mirrors the lecture pattern of querying the database and verifying the
        data appears correctly in the browser (Week13-Testing slide 31):
            elems = self.driver.find_elements(By.ID, student.uwa_id)
            self.assertEqual(len(elems), 1, ...)
        """
        self.driver.get(_HOST + f'/beats/{self._beat_id}')
        wait = WebDriverWait(self.driver, _WAIT)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'h1')))
        self.assertIn(
            'Selenium Test Beat', self.driver.page_source,
            'The seeded beat title must appear on the beat detail page',
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    unittest.main(verbosity=2)
