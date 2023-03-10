import argparse
import tempfile
import queue
import sys
import os
import sounddevice as sd
import soundfile as sf
import numpy 
assert numpy 
import openai
from rich import print
import keyboard
import threading
from datetime import datetime, timedelta
import time
import shutil
from static_vars import static_vars
from dotenv import load_dotenv

load_dotenv()

if os.getenv("API_KEY") is None:
    print("API_KEY not found in .env file")
    exit()

openai.api_key=os.getenv("API_KEY")
SHORT_NORMALIZE = (1.0/32768.0)

def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except ValueError:
        return text

def gpt_transcript(file_path):
    audio_file = open(file_path, "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file)
    return transcript["text"]

def rms(frame):
    count = len(frame)/swidth
    format = "%dh"%(count)
    shorts = struct.unpack( format, frame )

    sum_squares = 0.0
    for sample in shorts:
        n = sample * SHORT_NORMALIZE
        sum_squares += n*n
    rms = math.pow(sum_squares/count,0.5)
    return rms * 1000

def send_api_request(filename):
    if not os.path.exists(filename):
        return
    length = 0
    with sf.SoundFile(filename, 'r') as f:
        length = len(f) / f.samplerate
    if length < 1:
        os.remove(filename)
        return
    text = gpt_transcript(filename)
    print(text)
    return

def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        '-l', '--list-devices', action='store_true',
        help='show list of audio devices and exit')
    args, remaining = parser.parse_known_args()
    if args.list_devices:
        print(sd.query_devices())
        parser.exit(0)
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parser])
    parser.add_argument(
        '-d', '--device', type=int_or_str,
        help='input device (numeric ID or substring)')
    parser.add_argument(
        '-r', '--samplerate', type=int, help='sampling rate')
    parser.add_argument(
        '-c', '--channels', type=int, default=1, help='number of input channels')
    parser.add_argument(
        '-s', '--subtype', type=str, help='sound file subtype (e.g. "PCM_24")')
    parser.add_argument(
        "-t", "--threshold", type=float, help="RMS threshold for detecting sound (default: 0.01)", default=0.01)
    args = parser.parse_args(remaining)
    q = queue.Queue()
    
    if args.samplerate is None:
        device_info = sd.query_devices(args.device, 'input')
        # soundfile expects an int, sounddevice provides a float:
        args.samplerate = int(device_info['default_samplerate'])
    
    try:
        if not os.path.exists('record'):
            os.makedirs('record')
        while True:
            cmd = input("Enter the command: ")

            if cmd== "s":
                stop_recording = False
                try:
                    print('#' * 80)
                    print('press Ctrl+C to stop the recording')
                    print('#' * 80)

                    @static_vars(last_sound_time=None, isBreak=False)
                    def callback(indata, frames, time, status):
                        if status:
                            print(status, file=sys.stderr)
                        q.put(indata.copy())
                        rms = numpy.sqrt(numpy.mean(indata**2))
                        if rms > args.threshold:
                            callback.last_sound_time = datetime.now()
                        else:
                            if callback.last_sound_time is not None and (datetime.now() - callback.last_sound_time).total_seconds() > 0.8:
                                callback.last_sound_time = None
                                callback.isBreak = True

                    def open_new_file(q):
                        filename = "./record/" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".wav"
                        with sf.SoundFile(filename, mode='x', samplerate=args.samplerate,
                            channels=args.channels) as file:
                            while True:
                                if q.empty():
                                    break
                                file.write(q.get())
                        send_api_request(filename)
                        return
                    with sd.InputStream(samplerate=args.samplerate, device=args.device,
                        channels=args.channels, callback=callback) as stream:
                        while not stop_recording:
                            while not callback.isBreak:
                                time.sleep(0.5)
                            t = threading.Thread(target=open_new_file, args=(q,))
                            t.start()
                            q = queue.Queue()
                            callback.isBreak = False

                except KeyboardInterrupt:
                    stop_recording = True
                    print("Press 's' to start recording again")
                    print("Press 'q' to quit")
            if cmd== "q":
                shutil.rmtree('record')
                exit()
    except Exception as e:
        parser.exit(type(e).__name__ + ': ' + str(e))

if __name__ == "__main__":
    main()