import io
import logging
import queue
import threading
import wave
import pyaudio

logger = logging.getLogger(__name__)


class AudioDevice:
    def __init__(self, output_device: int = -1):
        self._p = pyaudio.PyAudio()

        if isinstance(output_device, int):
            if output_device < 0:
                output_device_info = self.get_default_output_device_info()
                output_device = output_device_info["index"]
            else:
                output_device_info = self.get_device_info(output_device)
        elif isinstance(output_device, str):
            output_device_info = self.get_output_device_by_name(output_device)
            if output_device_info is None:
                output_device_info = self.get_default_output_device_info()
            output_device = output_device_info["index"]

        self.output_device = output_device
        self.output_device_info = output_device_info

    def normalize_device_info(self, info: dict) -> dict:
        normalized = {
            "index": info.get("index"),
            "name": info.get("name"),
            "max_output_channels": info.get("maxOutputChannels"),
            "default_sample_rate": info.get("defaultSampleRate")
        }
        return normalized

    def get_default_output_device_info(self) -> dict:
        try:
            info = self._p.get_default_output_device_info()
            info["index"] = info.get("index", 0)
            return self.normalize_device_info(info)
        except Exception as ex:
            devices = self.get_audio_devices()
            for d in devices:
                if d["max_output_channels"] > 0:
                    return d
            raise Exception("Output devices not found")

    def get_device_info(self, index: int) -> dict:
        info = self._p.get_device_info_by_index(index)
        info["index"] = index
        return self.normalize_device_info(info)

    def get_output_device_by_name(self, name: str) -> dict:
        for d in self.get_audio_devices():
            if d["max_output_channels"] > 0 and name.lower() in d["name"].lower():
                return d
        return None

    def get_output_device_with_prompt(self, prompt: str = None) -> dict:
        print("==== Output devices ====")
        for d in self.get_audio_devices():
            if d["max_output_channels"] > 0:
                print(f'{d["index"]}: {d["name"]}')
        idx = input(prompt or "Output device index (Skip to use default): ")
        if idx.strip() == "":
            return self.get_default_output_device_info()
        else:
            return self.get_device_info(int(idx.strip()))

    def get_audio_devices(self) -> list:
        devices = []
        count = self._p.get_device_count()
        for i in range(count):
            info = self._p.get_device_info_by_index(i)
            info["index"] = i
            devices.append(self.normalize_device_info(info))
        return devices

    def list_audio_devices(self):
        for d in self.get_audio_devices():
            print(d)

    def terminate(self):
        self._p.terminate()


class AudioPlayer:
    def __init__(self, device_index: int, chunk_size: int = 1024):
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self.process_queue, daemon=True)
        self.thread.start()

        self.to_wave = None
        self.p = pyaudio.PyAudio()
        self.play_stream = None
        self.device_index = device_index
        self.chunk_size = chunk_size

        self.wave_params = None
        self.is_playing = False
        self.stop_event = threading.Event()

    def is_wave_params_changed(self, current_params: wave._wave_params):
        return self.wave_params is None or current_params is None \
            or self.wave_params.nchannels != current_params.nchannels \
            or self.wave_params.sampwidth != current_params.sampwidth \
            or self.wave_params.framerate != current_params.framerate

    def initilize_stream(self, sample_rate: int, channels: int, sample_width: int, wave_params: wave._wave_params = None):
        if self.play_stream:
            self.play_stream.stop_stream()
            self.play_stream.close()
            self.play_stream = None

        self.wave_params = wave_params
        self.play_stream = self.p.open(
            format=self.p.get_format_from_width(sample_width),
            channels=channels,
            rate=sample_rate,
            output=True,
            output_device_index=self.device_index,
            frames_per_buffer=self.chunk_size
        )

    def play(self, content: bytes):
        try:
            self.stop_event.clear()
            self.is_playing = True

            if self.to_wave:
                wave_content = self.to_wave(content)
            else:
                wave_content = content

            if wave_content:
                with wave.open(io.BytesIO(wave_content), "rb") as wf:
                    current_params = wf.getparams()
                    if not self.play_stream or self.is_wave_params_changed(current_params):
                        self.initilize_stream(
                            sample_rate=current_params.framerate,
                            channels=current_params.nchannels,
                            sample_width=current_params.sampwidth,
                            wave_params=current_params
                        )

                    data = wf.readframes(self.chunk_size)
                    while data:
                        if self.stop_event.is_set():
                            break
                        self.play_stream.write(data)
                        data = wf.readframes(self.chunk_size)

        except Exception as ex:
            logger.error(f"Error at play: {ex}", exc_info=True)

        finally:
            self.is_playing = False

    def process_queue(self):
        while True:
            data, has_wave_header = self.queue.get()
            if data is None:
                break
            self.is_playing = True
            if has_wave_header:
                self.play(data)
            else:
                self.play_stream.write(data)
            self.is_playing = False

    def add(self, audio_bytes: bytes, has_wave_header: bool = False):
        self.queue.put((audio_bytes, has_wave_header))

    def stop(self):
        while not self.queue.empty():
            self.queue.get()
        self.stop_event.set()
