import math
import os
import queue
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "錄音檔分割工具"
SUPPORTED_INPUT_EXTS = [
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma", ".aiff", ".aif",
    ".amr", ".mka", ".mp4", ".mov", ".mkv", ".webm", ".3gp", ".ts", ".m2ts"
]
OUTPUT_EXT_OPTIONS = ["keep", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"]


def format_seconds(total_seconds: float) -> str:
    total_seconds = max(0, int(round(total_seconds)))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def parse_hms(text: str) -> int:
    text = text.strip()
    if not text:
        raise ValueError("時間欄位不能為空")

    if text.isdigit():
        return int(text)

    parts = text.split(":")
    if len(parts) not in (2, 3):
        raise ValueError("時間格式請輸入秒數，或 HH:MM:SS / MM:SS")

    try:
        nums = [int(p) for p in parts]
    except ValueError as exc:
        raise ValueError("時間格式含有非數字內容") from exc

    if len(nums) == 2:
        minutes, seconds = nums
        hours = 0
    else:
        hours, minutes, seconds = nums

    if minutes < 0 or seconds < 0 or hours < 0:
        raise ValueError("時間不能為負數")
    if minutes >= 60 or seconds >= 60:
        raise ValueError("分鐘與秒數需小於 60")

    return hours * 3600 + minutes * 60 + seconds


@dataclass
class SplitJob:
    input_file: Path
    output_dir: Path
    mode: str
    parts: int | None
    segment_seconds: int | None
    max_parts: int | None
    output_ext: str


class FFmpegHelper:
    @staticmethod
    def ffmpeg_path() -> str | None:
        return shutil.which("ffmpeg")

    @staticmethod
    def ffprobe_path() -> str | None:
        return shutil.which("ffprobe")

    @staticmethod
    def check_available() -> tuple[bool, str]:
        ffmpeg = FFmpegHelper.ffmpeg_path()
        ffprobe = FFmpegHelper.ffprobe_path()
        if ffmpeg and ffprobe:
            return True, "已找到 ffmpeg / ffprobe"
        return False, (
            "找不到 ffmpeg 或 ffprobe。\n\n"
            "請先安裝 FFmpeg 並加入系統 PATH。\n"
            "Windows 可安裝 ffmpeg 後重新開啟程式。\n"
            "macOS 可用 brew install ffmpeg\n"
            "Ubuntu / Debian 可用 sudo apt install ffmpeg"
        )

    @staticmethod
    def get_duration_seconds(input_file: Path) -> float:
        ffprobe = FFmpegHelper.ffprobe_path()
        if not ffprobe:
            raise RuntimeError("找不到 ffprobe")

        cmd = [
            ffprobe,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(input_file),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        raw = result.stdout.strip()
        if not raw:
            raise RuntimeError("無法讀取檔案時長")
        return float(raw)


class AudioSplitterGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("900x700")
        self.root.minsize(860, 640)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.is_running = False

        self.input_path_var = tk.StringVar()
        self.output_dir_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="parts")
        self.parts_var = tk.StringVar(value="4")
        self.segment_var = tk.StringVar(value="00:10:00")
        self.max_parts_var = tk.StringVar(value="")
        self.output_ext_var = tk.StringVar(value="keep")
        self.file_info_var = tk.StringVar(value="尚未選擇檔案")
        self.ffmpeg_status_var = tk.StringVar(value="檢查 ffmpeg 中...")
        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="待命中")

        self._build_ui()
        self._check_ffmpeg_async()
        self._poll_log_queue()

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=14)
        main.pack(fill="both", expand=True)

        title = ttk.Label(main, text=APP_TITLE, font=("Microsoft JhengHei UI", 18, "bold"))
        title.pack(anchor="w", pady=(0, 10))

        desc = ttk.Label(
            main,
            text=(
                "支援多種錄音 / 音訊 / 含音訊影片格式。可平均切成 N 份，或用固定時長切檔。\n"
                "固定時長模式可另外限制最多輸出幾份。時間格式可輸入秒數，或 HH:MM:SS / MM:SS。"
            ),
            justify="left"
        )
        desc.pack(anchor="w", pady=(0, 12))

        input_frame = ttk.LabelFrame(main, text="1. 選擇檔案與輸出位置", padding=12)
        input_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(input_frame, text="輸入檔案").grid(row=0, column=0, sticky="w")
        ttk.Entry(input_frame, textvariable=self.input_path_var, width=78).grid(row=0, column=1, padx=8, sticky="ew")
        ttk.Button(input_frame, text="瀏覽", command=self.choose_input_file).grid(row=0, column=2)

        ttk.Label(input_frame, text="輸出資料夾").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(input_frame, textvariable=self.output_dir_var, width=78).grid(row=1, column=1, padx=8, pady=(8, 0), sticky="ew")
        ttk.Button(input_frame, text="選擇", command=self.choose_output_dir).grid(row=1, column=2, pady=(8, 0))

        ttk.Label(input_frame, textvariable=self.file_info_var, foreground="#1f4d7a").grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(10, 0)
        )
        ttk.Label(input_frame, textvariable=self.ffmpeg_status_var).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(6, 0)
        )

        input_frame.columnconfigure(1, weight=1)

        mode_frame = ttk.LabelFrame(main, text="2. 分割方式", padding=12)
        mode_frame.pack(fill="x", pady=(0, 10))

        ttk.Radiobutton(
            mode_frame,
            text="平均分成幾份",
            variable=self.mode_var,
            value="parts",
            command=self._refresh_mode_state
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(mode_frame, text="份數").grid(row=0, column=1, sticky="e", padx=(16, 6))
        self.parts_entry = ttk.Entry(mode_frame, textvariable=self.parts_var, width=12)
        self.parts_entry.grid(row=0, column=2, sticky="w")

        ttk.Radiobutton(
            mode_frame,
            text="每段固定時間",
            variable=self.mode_var,
            value="duration",
            command=self._refresh_mode_state
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Label(mode_frame, text="每段長度").grid(row=1, column=1, sticky="e", padx=(16, 6), pady=(10, 0))
        self.segment_entry = ttk.Entry(mode_frame, textvariable=self.segment_var, width=12)
        self.segment_entry.grid(row=1, column=2, sticky="w", pady=(10, 0))
        ttk.Label(mode_frame, text="例：600 或 00:10:00").grid(row=1, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(mode_frame, text="最多輸出份數（可空白）").grid(row=2, column=1, sticky="e", padx=(16, 6), pady=(10, 0))
        self.max_parts_entry = ttk.Entry(mode_frame, textvariable=self.max_parts_var, width=12)
        self.max_parts_entry.grid(row=2, column=2, sticky="w", pady=(10, 0))

        out_frame = ttk.LabelFrame(main, text="3. 輸出設定", padding=12)
        out_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(out_frame, text="輸出副檔名").grid(row=0, column=0, sticky="w")
        self.output_ext_combo = ttk.Combobox(
            out_frame,
            textvariable=self.output_ext_var,
            values=OUTPUT_EXT_OPTIONS,
            width=12,
            state="readonly"
        )
        self.output_ext_combo.grid(row=0, column=1, padx=(8, 0), sticky="w")
        ttk.Label(
            out_frame,
            text="keep = 保持原始副檔名；若原始為影片容器，也可轉出成純音訊格式"
        ).grid(row=0, column=2, padx=(10, 0), sticky="w")

        run_frame = ttk.Frame(main)
        run_frame.pack(fill="x", pady=(8, 8))

        self.start_button = ttk.Button(run_frame, text="開始分割", command=self.start_split)
        self.start_button.pack(side="left")
        ttk.Button(run_frame, text="清空紀錄", command=self.clear_log).pack(side="left", padx=(8, 0))

        self.progress_bar = ttk.Progressbar(run_frame, maximum=100, variable=self.progress_var)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(16, 0))

        ttk.Label(main, textvariable=self.status_var).pack(anchor="w", pady=(0, 8))

        log_frame = ttk.LabelFrame(main, text="執行紀錄", padding=8)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, height=18, wrap="word", font=("Consolas", 10))
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)
        self.log_text.insert("end", "程式已啟動。\n")
        self.log_text.config(state="disabled")

        note = ttk.Label(
            main,
            text=(
                "提醒：此工具需要電腦已安裝 ffmpeg。若你要我，我也可以再幫你做一版打包成 Windows exe 的版本。"
            )
        )
        note.pack(anchor="w", pady=(10, 0))

        self._refresh_mode_state()

    def _append_log(self, message: str):
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _poll_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self._append_log(msg)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_log_queue)

    def log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")

    def _check_ffmpeg_async(self):
        def runner():
            ok, msg = FFmpegHelper.check_available()
            self.ffmpeg_status_var.set(msg)
            self.log(msg)
            if not ok:
                self.status_var.set("尚未找到 ffmpeg / ffprobe")
        threading.Thread(target=runner, daemon=True).start()

    def _refresh_mode_state(self):
        is_parts = self.mode_var.get() == "parts"
        parts_state = "normal" if is_parts else "disabled"
        duration_state = "disabled" if is_parts else "normal"

        self.parts_entry.config(state=parts_state)
        self.segment_entry.config(state=duration_state)
        self.max_parts_entry.config(state=duration_state)

    def choose_input_file(self):
        filetypes = [("支援的音訊 / 影片", " ".join(f"*{ext}" for ext in SUPPORTED_INPUT_EXTS)), ("所有檔案", "*.*")]
        path = filedialog.askopenfilename(title="選擇錄音檔", filetypes=filetypes)
        if not path:
            return
        self.input_path_var.set(path)
        if not self.output_dir_var.get().strip():
            self.output_dir_var.set(str(Path(path).parent / f"{Path(path).stem}_split"))
        threading.Thread(target=self._update_file_info, daemon=True).start()

    def choose_output_dir(self):
        path = filedialog.askdirectory(title="選擇輸出資料夾")
        if path:
            self.output_dir_var.set(path)

    def _update_file_info(self):
        input_path = self.input_path_var.get().strip()
        if not input_path:
            self.file_info_var.set("尚未選擇檔案")
            return
        try:
            p = Path(input_path)
            size_mb = p.stat().st_size / (1024 * 1024)
            duration = FFmpegHelper.get_duration_seconds(p)
            self.file_info_var.set(
                f"檔名：{p.name} ｜ 大小：約 {size_mb:.2f} MB ｜ 長度：約 {format_seconds(duration)}"
            )
            self.log(f"已讀取檔案資訊：{p.name}，時長 {format_seconds(duration)}")
        except Exception as exc:
            self.file_info_var.set(f"已選擇：{Path(input_path).name}（暫時無法讀取詳細資訊）")
            self.log(f"讀取檔案資訊失敗：{exc}")

    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        self.log("已清空執行紀錄")

    def validate_job(self) -> SplitJob:
        input_file = Path(self.input_path_var.get().strip())
        output_dir = Path(self.output_dir_var.get().strip())
        mode = self.mode_var.get()
        output_ext = self.output_ext_var.get().strip() or "keep"

        if not input_file.exists() or not input_file.is_file():
            raise ValueError("請先選擇有效的輸入檔案")

        ok, msg = FFmpegHelper.check_available()
        if not ok:
            raise ValueError(msg)

        parts = None
        segment_seconds = None
        max_parts = None

        if mode == "parts":
            try:
                parts = int(self.parts_var.get().strip())
            except ValueError as exc:
                raise ValueError("份數請輸入正整數") from exc
            if parts <= 0:
                raise ValueError("份數必須大於 0")
        else:
            segment_seconds = parse_hms(self.segment_var.get())
            if segment_seconds <= 0:
                raise ValueError("每段長度必須大於 0")
            max_parts_raw = self.max_parts_var.get().strip()
            if max_parts_raw:
                try:
                    max_parts = int(max_parts_raw)
                except ValueError as exc:
                    raise ValueError("最多輸出份數請輸入正整數") from exc
                if max_parts <= 0:
                    raise ValueError("最多輸出份數必須大於 0")

        if output_ext not in OUTPUT_EXT_OPTIONS:
            raise ValueError("輸出副檔名不在支援列表中")

        return SplitJob(
            input_file=input_file,
            output_dir=output_dir,
            mode=mode,
            parts=parts,
            segment_seconds=segment_seconds,
            max_parts=max_parts,
            output_ext=output_ext,
        )

    def start_split(self):
        if self.is_running:
            messagebox.showinfo(APP_TITLE, "目前已有分割工作在執行中")
            return

        try:
            job = self.validate_job()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return

        self.is_running = True
        self.start_button.config(state="disabled")
        self.progress_var.set(0)
        self.status_var.set("分割中...")
        self.log("開始分割檔案")

        threading.Thread(target=self._run_split_job, args=(job,), daemon=True).start()

    def _set_finished(self):
        self.is_running = False
        self.start_button.config(state="normal")

    def _run_split_job(self, job: SplitJob):
        try:
            self._do_split(job)
            self.status_var.set("完成")
            self.log(f"完成，輸出資料夾：{job.output_dir}")
            messagebox.showinfo(APP_TITLE, f"分割完成！\n輸出資料夾：\n{job.output_dir}")
        except Exception as exc:
            self.status_var.set("失敗")
            self.log(f"錯誤：{exc}")
            messagebox.showerror(APP_TITLE, f"分割失敗：\n{exc}")
        finally:
            self.progress_var.set(100 if self.status_var.get() == "完成" else 0)
            self.root.after(0, self._set_finished)

    def _do_split(self, job: SplitJob):
        duration = FFmpegHelper.get_duration_seconds(job.input_file)
        if duration <= 0:
            raise RuntimeError("檔案時長為 0，無法分割")

        output_dir = job.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        if job.mode == "parts":
            assert job.parts is not None
            segment_seconds = math.ceil(duration / job.parts)
            total_parts = job.parts
            self.log(f"模式：平均分成 {job.parts} 份，每段約 {format_seconds(segment_seconds)}")
        else:
            assert job.segment_seconds is not None
            segment_seconds = job.segment_seconds
            computed_parts = math.ceil(duration / segment_seconds)
            total_parts = min(computed_parts, job.max_parts) if job.max_parts else computed_parts
            self.log(
                f"模式：每段 {format_seconds(segment_seconds)}，預計輸出 {total_parts} 份"
                + (f"（上限 {job.max_parts} 份）" if job.max_parts else "")
            )

        if total_parts <= 0:
            raise RuntimeError("計算後沒有可輸出的分段")

        source_suffix = job.input_file.suffix.lower() if job.input_file.suffix else ".mp3"
        out_suffix = source_suffix if job.output_ext == "keep" else job.output_ext
        base_name = job.input_file.stem
        ffmpeg = FFmpegHelper.ffmpeg_path()
        assert ffmpeg is not None

        for index in range(total_parts):
            start = index * segment_seconds
            if start >= duration:
                self.log(f"第 {index + 1} 段超出原始時長，停止輸出")
                break

            remaining = duration - start
            current_len = min(segment_seconds, remaining)
            if current_len <= 0:
                break

            out_name = f"{base_name}_part{index + 1:03d}{out_suffix}"
            out_path = output_dir / out_name
            self.log(
                f"輸出第 {index + 1} 段：起點 {format_seconds(start)}，長度 {format_seconds(current_len)} -> {out_name}"
            )

            cmd = [
                ffmpeg,
                "-y",
                "-ss", str(start),
                "-i", str(job.input_file),
                "-t", str(current_len),
                "-vn",
            ]

            audio_codec_args = self._build_output_codec_args(out_suffix)
            cmd.extend(audio_codec_args)
            cmd.append(str(out_path))

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(
                    f"第 {index + 1} 段輸出失敗。\n"
                    f"ffmpeg 訊息：{(result.stderr or '').strip()[:1200]}"
                )

            progress = ((index + 1) / total_parts) * 100
            self.progress_var.set(progress)
            self.status_var.set(f"進行中：{index + 1}/{total_parts}")

    @staticmethod
    def _build_output_codec_args(out_suffix: str) -> list[str]:
        out_suffix = out_suffix.lower()

        # keep 模式若維持原副檔名，仍統一重編碼，避免某些容器直接 copy 造成切段相容性問題。
        if out_suffix == ".mp3":
            return ["-acodec", "libmp3lame", "-q:a", "2"]
        if out_suffix == ".wav":
            return ["-acodec", "pcm_s16le"]
        if out_suffix in {".m4a", ".aac"}:
            return ["-acodec", "aac", "-b:a", "192k"]
        if out_suffix == ".flac":
            return ["-acodec", "flac"]
        if out_suffix in {".ogg", ".opus"}:
            codec = "libopus" if out_suffix == ".opus" else "libvorbis"
            return ["-acodec", codec, "-b:a", "160k"]
        return ["-acodec", "libmp3lame", "-q:a", "2"]


def main():
    root = tk.Tk()
    try:
        root.iconname(APP_TITLE)
    except Exception:
        pass
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    AudioSplitterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
