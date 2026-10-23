import json
import os
import re
import unittest

import helpers

SKIP_DIRS = {".git", "node_modules", "app", "_refs", "transcripts"}
EM_DASH = chr(0x2014)


def read(path):
    with open(path) as handle:
        return handle.read()


def walk(exts):
    for base, dirs, files in os.walk(helpers.REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith(exts):
                yield os.path.join(base, name)


class RepoFiles(unittest.TestCase):
    def test_json_files_parse(self):
        for path in walk((".json", ".jsonl")):
            for line in (read(path).splitlines() if path.endswith(".jsonl") else [read(path)]):
                if line.strip():
                    json.loads(line)

    def test_markdown_links_resolve(self):
        link = re.compile(r"\]\(([^)#\s]+)(#[^)]*)?\)")
        for path in walk((".md",)):
            for target, _ in link.findall(read(path)):
                if re.match(r"^[a-z]+:", target):
                    continue
                self.assertTrue(os.path.exists(os.path.join(os.path.dirname(path), target)), "%s -> %s" % (path, target))

    def test_no_em_dashes_in_text_we_wrote(self):
        for path in walk((".md", ".py", ".sh", ".yml", ".svg", ".example")):
            self.assertNotIn(EM_DASH, read(path), path)

    def test_no_secrets_committed(self):
        pattern = re.compile(r"(AQ\.[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|sk-or-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{30,})")
        for path in walk((".md", ".py", ".sh", ".yml", ".json", ".jsonl", ".example")):
            self.assertIsNone(pattern.search(read(path)), path)

    def test_notes_are_small(self):
        for name in os.listdir(os.path.join(helpers.REPO, "vault")):
            if name.endswith(".md"):
                self.assertLess(os.path.getsize(os.path.join(helpers.REPO, "vault", name)), 2000, name)


if __name__ == "__main__":
    unittest.main()
