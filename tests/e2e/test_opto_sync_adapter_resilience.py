import json
import os
import re
import tomllib
import unittest
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / "opto-sync-adapter.json"
MANIFEST_PATH = ROOT / ".zpkg.toml"
LOCK_PATH = ROOT / ".zpkg.lock"
INSTALL_ROOT = "zed_modules/opto-sync/opto-sync-clients"
EXPECTED_NATIVE = {"rust": ("opto-sync-client", "clients/rust"), "typescript": ("@opto-sync/client", "clients/ts"), "dart": ("opto_sync_client", "clients/dart"), "gleam": ("opto_sync_client", "clients/gleam")}
FORBIDDEN_COLLECTION_FRAGMENTS = {"password", "passwd", "secret", "access_token", "refresh_token", "otp", "private_key", "credential_bytes", "raw_audio", "media_bytes"}

def load_contract():
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    lock = tomllib.loads(LOCK_PATH.read_text(encoding="utf-8"))
    return profile, manifest, lock

class OptoSyncAdapterResilienceTest(unittest.TestCase):
    def test_dependency_and_install_root_are_canonical(self):
        profile, manifest, _ = load_contract()
        self.assertEqual(profile["schemaVersion"], 1)
        self.assertEqual(manifest["dependencies"]["opto-sync/opto-sync-clients"], "^0.2.0")
        self.assertEqual(manifest["install"]["dir"], "zed_modules")
        self.assertEqual(profile["dependency"], {"package": "opto-sync/opto-sync-clients", "range": "^0.2.0", "installRoot": INSTALL_ROOT})
        self.assertEqual(profile["repository"], os.environ.get("GITHUB_REPOSITORY", profile["repository"]))

    def test_native_adapters_are_unique_and_cannot_escape_install_root(self):
        profile, _, _ = load_contract(); seen = set()
        for language, adapter in profile["nativeAdapters"].items():
            self.assertIn(language, EXPECTED_NATIVE); package, suffix = EXPECTED_NATIVE[language]
            self.assertEqual(adapter["package"], package); path = PurePosixPath(adapter["path"])
            self.assertNotIn("..", path.parts); self.assertTrue(adapter["path"].startswith(f"{INSTALL_ROOT}/")); self.assertTrue(adapter["path"].endswith(suffix)); self.assertNotIn(adapter["path"], seen); seen.add(adapter["path"])

    def test_wrapper_boundary_is_nonempty_unique_and_not_engine_duplication(self):
        profile, _, _ = load_contract(); retained = profile["wrapperRetains"]; delegated = profile["delegatesToOptoSync"]
        self.assertGreaterEqual(len(retained), 3); self.assertGreaterEqual(len(delegated), 5); self.assertEqual(len(retained), len(set(retained))); self.assertEqual(len(delegated), len(set(delegated))); self.assertFalse(set(retained) & set(delegated))
        normalized = " ".join(delegated).lower()
        for concept in ("reconciliation", "mutation identity", "durable queue", "indexeddb", "sqlite", "checkpoint"): self.assertIn(concept, normalized)

    def test_product_collections_exclude_secret_or_blob_material(self):
        profile, _, _ = load_contract(); collections = profile["productCollections"]
        self.assertTrue(collections); self.assertEqual(len(collections), len(set(collections)))
        for collection in collections:
            for forbidden in FORBIDDEN_COLLECTION_FRAGMENTS: self.assertNotIn(forbidden, collection.lower())

    def test_persistence_and_authority_invariants_cover_every_tier(self):
        profile, _, _ = load_contract(); persistence = profile["persistence"]
        self.assertIn("indexeddb", persistence["web"]); self.assertTrue({"sqlite", "drift"} & set(persistence["mobile"])); self.assertTrue({"postgres", "supabase"} <= set(persistence["backend"]))
        for invariant in ("renderLocalView", "realtimeIsWakeHint", "serverCursorIsAuthoritative", "mutableGitRefsForbidden", "removeBespokeCoreOnlyAfterParity"): self.assertIs(profile["invariants"][invariant], True)

    def test_release_lock_is_empty_only_while_publication_is_blocked(self):
        profile, _, lock = load_contract(); packages = lock.get("package", [])
        if profile["releaseState"] == "blocked-until-certified-package-published": self.assertEqual(lock.get("version"), 1); self.assertEqual(packages, [])
        else:
            package = next(item for item in packages if item.get("org") == "opto-sync" and item.get("name") == "opto-sync-clients")
            self.assertRegex(package["sha256"], r"^[0-9a-f]{64}$"); self.assertRegex(package["vcs_commit"], r"^[0-9a-f]{40}$"); self.assertGreater(package["size"], 0)
            for field in ("version", "format", "vcs_tag", "source"): self.assertTrue(package[field])

    def test_no_mutable_release_reference_or_placeholder_provenance(self):
        profile, _, lock = load_contract(); serialized = json.dumps({"profile": profile, "lock": lock}).lower()
        for mutable in ("refs/heads/main", 'branch = "main"', '"latest"', "replace-me", "todo-sha", "deadbeef"): self.assertNotIn(mutable, serialized)
        for digest in re.findall(r'"sha256"\s*:\s*"([^"]+)"', serialized): self.assertRegex(digest, r"^[0-9a-f]{64}$")

if __name__ == "__main__": unittest.main()
