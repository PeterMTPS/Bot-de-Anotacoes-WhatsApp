import os
import tempfile
import unittest

os.environ["DB_PATH"] = tempfile.NamedTemporaryFile(delete=False).name

import app


class BotTest(unittest.TestCase):
    def setUp(self):
        app.store = app.NotesStore(os.environ["DB_PATH"])
        with app.store.connect() as conn:
            conn.execute("DELETE FROM notes")

    def test_saves_and_lists_notes(self):
        reply = app.handle_message("5511999999999", "comprar leite")

        self.assertIn("Anotado.", reply)
        self.assertIn("comprar leite", app.handle_message("5511999999999", "/listar"))

    def test_searches_notes(self):
        app.handle_message("5511999999999", "ideia de video")
        app.handle_message("5511999999999", "comprar arroz")

        reply = app.handle_message("5511999999999", "/buscar video")

        self.assertIn("ideia de video", reply)
        self.assertNotIn("comprar arroz", reply)

    def test_deletes_note(self):
        app.handle_message("5511999999999", "nota temporaria")
        listed = app.handle_message("5511999999999", "/listar")
        note_id = listed.split("#", 1)[1].split(" ", 1)[0]

        self.assertEqual(app.handle_message("5511999999999", f"/apagar {note_id}"), "Anotacao apagada.")
        self.assertNotIn("nota temporaria", app.handle_message("5511999999999", "/listar"))


if __name__ == "__main__":
    unittest.main()
