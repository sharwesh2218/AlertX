#!/usr/bin/env python3
"""
AlertX — One-Step Hugging Face Space Uploader
Bundles backend + frontend dashboard (including Sentinel Intel & AI models)
into a clean temporary folder and uploads directly to any Hugging Face Docker Space
using `huggingface_hub` (no `git-lfs` or `brew` required on macOS).
"""

import argparse
import getpass
import os
import shutil
import sys
import tempfile


SKIP_NAMES = {
    ".git",
    ".github",
    "__pycache__",
    "venv",
    "venv310",
    "uploads",
    "logs",
    "tests",
    ".env",
    ".recipient",
    ".DS_Store",
    "local_users.db",
    "alertx.db",
    "credentials.json",
    "serviceAccountKey.json",
}


def _is_raw_lfs_pointer(filepath: str) -> bool:
    """Detect unpulled Git LFS text pointer files so Hugging Face commit validation does not reject them."""
    try:
        if os.path.getsize(filepath) > 1024:
            return False
        with open(filepath, "rb") as f:
            head = f.read(45)
        return head.startswith(b"version https://git-lfs.github.com/spec/v1")
    except OSError:
        return False


def _copy_filtered(src_dir: str, dst_dir: str) -> None:
    os.makedirs(dst_dir, exist_ok=True)
    for entry in os.listdir(src_dir):
        if entry in SKIP_NAMES or entry.endswith(".pyc") or entry.endswith(".db"):
            continue
        src_path = os.path.join(src_dir, entry)
        dst_path = os.path.join(dst_dir, entry)
        if os.path.isdir(src_path):
            _copy_filtered(src_path, dst_path)
        elif os.path.isfile(src_path):
            if _is_raw_lfs_pointer(src_path):
                print(f"  [skip] Skipping placeholder LFS pointer: {entry}")
                continue
            shutil.copy2(src_path, dst_path)


def main() -> None:
    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("Missing `huggingface_hub`. Install it first with:")
        print("  python3 -m pip install --user huggingface_hub")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Upload AlertX + Sentinel to a Hugging Face Docker Space.")
    parser.add_argument("--space", help="Space repo ID as <hf-username>/<space-name> (e.g. chandru/AlertX)")
    parser.add_argument("--token", help="Hugging Face Write access token (starts with hf_...)")
    args = parser.parse_args()

    space_id = (args.space or os.getenv("HF_SPACE") or "").strip()
    if not space_id:
        space_id = input("Enter your Hugging Face Space ID (format: username/SpaceName): ").strip()
    if "/" not in space_id:
        print("Error: Space ID must look like `username/SpaceName` (e.g. `chandru/AlertX`).")
        sys.exit(1)

    token = (args.token or os.getenv("HF_TOKEN") or "").strip()
    if not token:
        token = getpass.getpass("Paste your Hugging Face Write Token (hf_...): ").strip()
    if not token:
        print("Error: Hugging Face token is required.")
        sys.exit(1)

    repo_root = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(repo_root, "backend")
    frontend_dir = os.path.join(repo_root, "frontend")

    staging_dir = tempfile.mkdtemp(prefix="alertx_hf_space_")
    try:
        print(f"1/3 Staging backend + AI models into {staging_dir} ...")
        _copy_filtered(backend_dir, staging_dir)

        print("2/3 Bundling frontend dashboard (with Sentinel Intel) into Space `/dashboard` ...")
        _copy_filtered(frontend_dir, os.path.join(staging_dir, "dashboard"))

        print(f"3/3 Uploading to Hugging Face Space `{space_id}` (large .pt/.h5 models may take 1-2 mins) ...")
        api = HfApi(token=token)
        api.upload_folder(
            folder_path=staging_dir,
            repo_id=space_id,
            repo_type="space",
            commit_message="Deploy full-stack AlertX + Sentinel Incident Intelligence",
        )

        owner, space_name = space_id.split("/", 1)
        direct_subdomain = f"{owner}-{space_name}".lower().replace("_", "-")
        print("\n✅ Upload complete! Hugging Face is now building your Docker container (takes ~5-8 mins first time).")
        print(f"   • Space App Page:   https://huggingface.co/spaces/{space_id}")
        print(f"   • Direct Full URL:  https://{direct_subdomain}.hf.space")
        print(f"   • Health Check:     https://{direct_subdomain}.hf.space/health")
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


if __name__ == "__main__":
    main()

