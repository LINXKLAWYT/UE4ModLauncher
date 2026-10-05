import os
import sys
import json
import time
import shutil
import tempfile
import subprocess
import threading
from datetime import datetime

from config import BASE_DIR, PROFILES_DIR, STATE_FILE

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    # Optional dependency. Without it, everything still works exactly like
    # before (wait only on the process we launched) - we just lose the
    # extra check that catches launcher-stub .exe files spawning the real
    # game and exiting early. `pip install psutil` to enable it.
    HAS_PSUTIL = False


class ModLogic:

    # ---------------- basic filesystem helpers ----------------

    @staticmethod
    def ensure_directories():
        if not os.path.exists(PROFILES_DIR):
            os.makedirs(PROFILES_DIR, exist_ok=True)

    @staticmethod
    def get_profiles():
        if not os.path.exists(PROFILES_DIR):
            return []
        return sorted(
            d for d in os.listdir(PROFILES_DIR)
            if os.path.isdir(os.path.join(PROFILES_DIR, d))
        )

    @staticmethod
    def get_profile_paths(profile_name):
        prof_dir = os.path.join(PROFILES_DIR, profile_name)
        return {
            "prof_dir": prof_dir,
            "cfg_file": os.path.join(prof_dir, "profile_config.json"),
            "mods_dir": os.path.join(prof_dir, "Mods"),
        }

    @staticmethod
    def delete_profile(profile_name):
        prof_dir = os.path.join(PROFILES_DIR, profile_name)
        if os.path.exists(prof_dir):
            shutil.rmtree(prof_dir, ignore_errors=True)

    @staticmethod
    def reset_appdata_keep_mods():
        """
        "Factory reset" of the AppData folder: wipes BASE_DIR (Profiles/,
        launcher_settings.json, launcher_state.json) and recreates it from
        scratch, but keeps every profile's mods. Only the Mods/ folder of
        each profile is preserved - not profile_config.json, not the
        settings file, not the crash-recovery state - so paths, language
        and the UUU toggle all go back to their defaults, but nobody's
        collected .pak files are thrown away.

        Returns {"success": bool, "profiles": [names restored], "error": str|None}
        """
        result = {"success": False, "profiles": [], "error": None}
        tmp_dir = None

        try:
            # 1. Back up every profile's Mods/ folder (only the folder
            #    itself - not profile_config.json) to a temp location.
            tmp_dir = tempfile.mkdtemp(prefix="UE4ModLauncher_backup_")
            profiles = ModLogic.get_profiles()
            for name in profiles:
                mods_dir = ModLogic.get_profile_paths(name)["mods_dir"]
                if os.path.isdir(mods_dir):
                    shutil.copytree(mods_dir, os.path.join(tmp_dir, name))

            # 2. Wipe the whole AppData folder for this app.
            if os.path.exists(BASE_DIR):
                shutil.rmtree(BASE_DIR)

            # 3. Recreate it from scratch.
            os.makedirs(PROFILES_DIR, exist_ok=True)

            # 4. Recreate each profile with a fresh/empty config, and
            #    restore its mods from the backup.
            for name in profiles:
                prof_dir = os.path.join(PROFILES_DIR, name)
                mods_dir = os.path.join(prof_dir, "Mods")
                os.makedirs(mods_dir, exist_ok=True)
                with open(os.path.join(prof_dir, "profile_config.json"), 'w', encoding='utf-8') as f:
                    json.dump({"exe_path": "", "paks_path": ""}, f, indent=4)

                backup_mods_dir = os.path.join(tmp_dir, name)
                if os.path.isdir(backup_mods_dir):
                    for fname in os.listdir(backup_mods_dir):
                        if fname.endswith('.pak'):
                            shutil.move(os.path.join(backup_mods_dir, fname), os.path.join(mods_dir, fname))

                result["profiles"].append(name)

            result["success"] = True
        except OSError as e:
            result["error"] = str(e)
        finally:
            if tmp_dir and os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)

        return result

    @staticmethod
    def open_profile_folder(profile_name):
        """Opens the profile's local Mods folder (inside AppData) in the
        system file explorer, so the user can drag mods in/out by hand if
        they want to, without having to know where AppData is."""
        mods_dir = ModLogic.get_profile_paths(profile_name)["mods_dir"]
        try:
            os.makedirs(mods_dir, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(mods_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", mods_dir])
            else:
                subprocess.Popen(["xdg-open", mods_dir])
            return True
        except OSError:
            return False

    @staticmethod
    def add_mods_to_profile(profile_name, file_paths):
        """
        Copies the given .pak files into the profile's local Mods folder
        (leaving the originals where they were - e.g. a Downloads folder -
        untouched). This is what the app's "Add mods" button uses, so mods
        never have to be moved into AppData by hand.
        Returns (added: list[str], failed: list[tuple[str, str]]).
        """
        mods_dir = ModLogic.get_profile_paths(profile_name)["mods_dir"]
        added, failed = [], []
        try:
            os.makedirs(mods_dir, exist_ok=True)
        except OSError as e:
            return added, [(mods_dir, str(e))]

        for src in file_paths:
            if not src.lower().endswith('.pak'):
                continue
            name = os.path.basename(src)
            dst = os.path.join(mods_dir, name)
            try:
                if os.path.exists(dst) and os.path.samefile(src, dst):
                    continue  # already there
            except OSError:
                pass  # samefile can fail harmlessly if dst doesn't exist yet
            try:
                shutil.copy2(src, dst)
                added.append(name)
            except OSError as e:
                failed.append((name, str(e)))

        return added, failed

    # ---------------- mod moving (hardened) ----------------

    @staticmethod
    def move_mods(source, destination):
        """
        Move every .pak file from `source` into `destination`.

        Unlike the original version, this never raises: a missing source
        folder is treated as "nothing to move" instead of crashing, and a
        single file that can't be moved (e.g. still locked by the game, or
        a permissions issue) is recorded and skipped instead of aborting
        the rest of the batch.

        Returns (moved: list[str], failed: list[tuple[str, str]]).
        """
        moved, failed = [], []

        if not os.path.exists(source):
            return moved, failed

        try:
            os.makedirs(destination, exist_ok=True)
        except OSError as e:
            failed.append((destination, str(e)))
            return moved, failed

        for file in os.listdir(source):
            if not file.endswith('.pak'):
                continue
            src_path = os.path.join(source, file)
            dst_path = os.path.join(destination, file)
            try:
                if os.path.exists(dst_path):
                    os.remove(dst_path)  # clear a stale duplicate blocking the move
                shutil.move(src_path, dst_path)
                moved.append(file)
            except OSError as e:
                failed.append((file, str(e)))

        return moved, failed

    @staticmethod
    def _move_selected_mods(source, destination, selected_files):
        """Move only explicitly selected .pak files, leaving other mods stored."""
        moved, failed = [], []
        try:
            os.makedirs(destination, exist_ok=True)
        except OSError as e:
            return moved, [(destination, str(e))]
        for filename in selected_files:
            if not isinstance(filename, str) or not filename.lower().endswith('.pak'):
                continue
            src_path = os.path.join(source, filename)
            dst_path = os.path.join(destination, filename)
            if not os.path.isfile(src_path):
                continue
            try:
                if os.path.exists(dst_path):
                    os.remove(dst_path)
                shutil.move(src_path, dst_path)
                moved.append(filename)
            except OSError as e:
                failed.append((filename, str(e)))
        return moved, failed

    @staticmethod
    def _move_selected_mods_with_retry(source, destination, selected_files, attempts=3, delay=1.5):
        moved_total, failed_total = [], []
        remaining = list(selected_files)
        for attempt in range(attempts):
            moved, failed = ModLogic._move_selected_mods(source, destination, remaining)
            moved_total.extend(moved)
            failed_total = failed
            if not failed or attempt == attempts - 1:
                break
            remaining = [name for name, _ in failed]
            time.sleep(delay)
        return moved_total, failed_total

    @staticmethod
    def _move_mods_with_retry(source, destination, attempts=3, delay=1.5):
        """
        Same as move_mods, but retries files that failed to move. This
        matters most right after the game closes: on Windows a file can
        stay briefly locked (antivirus scan, delayed handle release) even
        though the process has already exited.
        """
        total_moved, last_failed = [], []
        for _ in range(attempts):
            moved, failed = ModLogic.move_mods(source, destination)
            total_moved.extend(moved)
            last_failed = failed
            if not failed:
                break
            time.sleep(delay)
        return total_moved, last_failed

    @staticmethod
    def _move_specific_files(source, destination, filenames):
        """Move only the named files (used by crash recovery, so we never
        sweep up unrelated .pak files someone may have dropped into the
        game's mods folder by hand)."""
        moved, failed = [], []
        if not filenames:
            return moved, failed
        try:
            os.makedirs(destination, exist_ok=True)
        except OSError as e:
            return moved, [(destination, str(e))]

        for file in filenames:
            src_path = os.path.join(source, file)
            if not os.path.exists(src_path):
                continue  # already not there - nothing to recover
            dst_path = os.path.join(destination, file)
            try:
                if os.path.exists(dst_path):
                    os.remove(dst_path)
                shutil.move(src_path, dst_path)
                moved.append(file)
            except OSError as e:
                failed.append((file, str(e)))
        return moved, failed

    # ---------------- crash-recovery state file ----------------

    @staticmethod
    def _write_state(profile_name, mods_dir, game_mods_folder, files):
        try:
            with open(STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    "profile": profile_name,
                    "mods_dir": mods_dir,
                    "game_mods_folder": game_mods_folder,
                    "files": files,
                    "timestamp": datetime.now().isoformat(),
                }, f, indent=4)
        except OSError:
            pass  # best effort - recovery just won't be possible next time

    @staticmethod
    def _clear_state():
        try:
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE)
        except OSError:
            pass

    @staticmethod
    def recover_pending_state():
        """
        Call this once on launcher startup. If a previous session was
        interrupted (crash, force-quit, power loss, task-killed) while its
        mods were still deployed inside the game's ~mods folder, this moves
        them back into the right profile automatically instead of leaving
        them stranded (or silently "lost" from the launcher's point of
        view).

        Returns None if there was nothing to recover, otherwise a dict:
        {"profile": str, "recovered": [...], "failed": [...]}
        """
        if not os.path.exists(STATE_FILE):
            return None

        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
        except (OSError, json.JSONDecodeError):
            ModLogic._clear_state()
            return None

        game_mods_folder = state.get("game_mods_folder")
        mods_dir = state.get("mods_dir")
        files = state.get("files", [])

        result = {"profile": state.get("profile"), "recovered": [], "failed": []}

        if game_mods_folder and mods_dir and files and os.path.exists(game_mods_folder):
            moved, failed = ModLogic._move_specific_files(game_mods_folder, mods_dir, files)
            result["recovered"] = moved
            result["failed"] = failed

        ModLogic._clear_state()
        return result

    # ---------------- waiting for the game to actually close ----------------

    @staticmethod
    def _guess_install_root(exe_path, levels_up=3):
        root = os.path.dirname(os.path.abspath(exe_path))
        for _ in range(levels_up):
            parent = os.path.dirname(root)
            if not parent or parent == root:
                break
            root = parent
        return root

    @staticmethod
    def _wait_for_process(exe_path, popen_proc, poll_interval=2):
        """
        subprocess only tells us when the process *we* started exits. Many
        UE4 games ship a thin launcher/anti-cheat stub .exe that spawns the
        real shipping executable and then exits itself within seconds - if
        we trust that exit, mods get moved back while the game is still
        running (or hasn't even finished loading them). If psutil is
        installed, we additionally wait until no process belonging to the
        same game install folder is still running.
        """
        popen_proc.wait()

        if not HAS_PSUTIL:
            return

        try:
            time.sleep(poll_interval)

            install_root = os.path.normcase(ModLogic._guess_install_root(exe_path))
            if len(install_root.rstrip(os.sep)) <= 3:
                return  # too shallow a path (e.g. a drive root) - unsafe to match on

            def matches(p):
                exe = p.info.get('exe') or ''
                return bool(exe) and os.path.normcase(exe).startswith(install_root)

            while True:
                still_running = False
                for p in psutil.process_iter(['name', 'exe']):
                    try:
                        if matches(p):
                            still_running = True
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                if not still_running:
                    break
                time.sleep(poll_interval)
        except Exception:
            # This is a best-effort safety net - never let it break launching.
            return


    # ---------------- main entry point ----------------

    @staticmethod
    def launch_game(profile_name):
        """
        Deploys the profile's mods, runs the game, and moves the mods back.
        Wrapped in try/finally so the "move back" step ALWAYS runs, even if
        the game fails to launch or something raises while waiting for it -
        the original version skipped this step entirely on any error,
        which is how mods ended up permanently stuck in the game folder.

        Returns a dict:
        {
          "success": bool, "error": str | None,
          "moved_in": [...], "moved_out": [...],
          "failed_in": [(file, err)...], "failed_out": [(file, err)...],
        }
        """
        result = {
            "success": False, "error": None,
            "moved_in": [], "moved_out": [],
            "failed_in": [], "failed_out": [],
        }

        paths = ModLogic.get_profile_paths(profile_name)
        cfg_file, mods_dir = paths["cfg_file"], paths["mods_dir"]

        if not os.path.exists(cfg_file):
            result["error"] = "missing_config"
            return result

        try:
            with open(cfg_file, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            result["error"] = f"bad_config: {e}"
            return result

        exe_path = cfg.get("exe_path")
        paks_path = cfg.get("paks_path")

        if not exe_path or not paks_path:
            result["error"] = "missing_paths"
            return result
        if not os.path.exists(exe_path):
            result["error"] = "exe_not_found"
            return result
        if not os.path.exists(paks_path):
            result["error"] = "paks_not_found"
            return result

        game_mods_folder = os.path.join(paks_path, "~mods")

        # Deploy only the mods selected in the launcher. Older profiles without
        # selected_mods retain the previous behaviour (all mods enabled).
        selected_mods = cfg.get("selected_mods")
        if selected_mods is None:
            selected_mods = [f for f in os.listdir(mods_dir) if f.lower().endswith('.pak')] if os.path.isdir(mods_dir) else []
        moved_in, failed_in = ModLogic._move_selected_mods_with_retry(
            mods_dir, game_mods_folder, selected_mods, attempts=2, delay=1.0
        )
        result["moved_in"], result["failed_in"] = moved_in, failed_in

        if moved_in:
            # Record what we deployed and where, so a crash mid-session can
            # be recovered from on the next launcher startup.
            ModLogic._write_state(profile_name, mods_dir, game_mods_folder, moved_in)

        try:
            proc = subprocess.Popen([exe_path])
            ModLogic._wait_for_process(exe_path, proc)
            result["success"] = True
        except Exception as e:
            result["error"] = f"launch_failed: {e}"
        finally:
            # 3. ALWAYS move mods back, whether the game closed normally,
            # failed to launch, or something above raised an exception.
            moved_out, failed_out = ModLogic._move_mods_with_retry(game_mods_folder, mods_dir, attempts=4, delay=1.5)
            result["moved_out"], result["failed_out"] = moved_out, failed_out
            ModLogic._clear_state()

        return result
