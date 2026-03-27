import json
import tempfile
import unittest
from pathlib import Path

import main


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_data_file = Path(self.temp_dir.name) / "profiles.json"

        self.original_data_file = main.DATA_FILE
        self.original_profiles = main.profiles

        self.test_profiles = main.default_profiles()
        main.DATA_FILE = self.temp_data_file
        main.profiles = self.test_profiles.copy()
        main.save_profiles(main.profiles)

        main.app.config["TESTING"] = True
        self.client = main.app.test_client()

    def get_csrf_token(self, path="/"):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)

        with self.client.session_transaction() as session:
            return session["csrf_token"]

    def tearDown(self):
        main.DATA_FILE = self.original_data_file
        main.profiles = self.original_profiles
        self.temp_dir.cleanup()

    def test_index_shows_profiles(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Hitta rätt profil snabbare.", html)
        self.assertIn("Anna Berg", html)
        self.assertIn("34 år", html)

    def test_admin_add_requires_login(self):
        response = self.client.get("/admin/add", follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Logga in som admin för att hantera profiler.", html)
        self.assertIn("Logga in som admin", html)

    def test_admin_login_and_logout(self):
        csrf_token = self.get_csrf_token("/")
        response = self.client.post(
            "/admin/login",
            data={
                "username": "admin",
                "password": "admin123",
                "csrf_token": csrf_token,
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Admin är nu inloggad.", response.get_data(as_text=True))

        response = self.client.post(
            "/admin/logout",
            data={"csrf_token": csrf_token},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Du är nu utloggad.", response.get_data(as_text=True))

    def test_admin_can_add_and_delete_profile(self):
        csrf_token = self.get_csrf_token("/")
        self.client.post(
            "/admin/login",
            data={
                "username": "admin",
                "password": "admin123",
                "csrf_token": csrf_token,
            },
            follow_redirects=True,
        )

        csrf_token = self.get_csrf_token("/admin/add")
        response = self.client.post(
            "/admin/add",
            data={
                "namn": "Test Person",
                "alder": "27",
                "utbildning": "Frontendutbildning",
                "erfarenheter": "3 års erfarenhet av webbproduktion",
                "beskrivning": "Lugn och noggrann person med intresse för tydliga gränssnitt.",
                "csrf_token": csrf_token,
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Profilen för Test Person lades till.", html)
        self.assertIn("Test Person", html)

        saved_profiles = json.loads(self.temp_data_file.read_text(encoding="utf-8"))
        added_profile = next(
            profile for profile in saved_profiles if profile["namn"] == "Test Person"
        )

        response = self.client.post(
            f"/admin/delete/{added_profile['id']}",
            data={"csrf_token": csrf_token},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Profilen togs bort.", html)
        self.assertNotIn("Test Person", html)

        saved_profiles = json.loads(self.temp_data_file.read_text(encoding="utf-8"))
        self.assertFalse(
            any(profile["namn"] == "Test Person" for profile in saved_profiles)
        )

    def test_post_without_csrf_token_is_rejected(self):
        response = self.client.post(
            "/admin/login",
            data={"username": "admin", "password": "admin123"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Din session kunde inte verifieras. Försök igen.",
            response.get_data(as_text=True),
        )

    def test_invalid_age_is_rejected(self):
        csrf_token = self.get_csrf_token("/")
        self.client.post(
            "/admin/login",
            data={
                "username": "admin",
                "password": "admin123",
                "csrf_token": csrf_token,
            },
            follow_redirects=True,
        )

        csrf_token = self.get_csrf_token("/admin/add")
        response = self.client.post(
            "/admin/add",
            data={
                "namn": "För Ung",
                "alder": "12",
                "utbildning": "Testutbildning",
                "erfarenheter": "Ingen relevant erfarenhet",
                "beskrivning": "Ska inte sparas.",
                "csrf_token": csrf_token,
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Ålder måste vara ett heltal mellan 16 och 100.", html)

        saved_profiles = json.loads(self.temp_data_file.read_text(encoding="utf-8"))
        self.assertFalse(any(profile["namn"] == "För Ung" for profile in saved_profiles))


if __name__ == "__main__":
    unittest.main()
