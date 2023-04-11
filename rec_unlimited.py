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
import subprocess
import moviepy.editor as mp
import tiktoken

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

def count_tokens(string: str):
    enc = tiktoken.get_encoding("cl100k_base")
    num_tokens = len(enc.encode(string))
    return num_tokens


def split_video(video_path, duration, chunk_size):
    video = mp.VideoFileClip(video_path)
    chunks = []

    for i in range(0, duration, chunk_size):
        start = i
        end = min(i + chunk_size, duration)
        chunk = video.subclip(start, end)
        chunks.append(chunk)

    return chunks

def gpt_large_file_transcript(file_path, ext="mp3", chunk_size=5 * 60):
    video = mp.VideoFileClip(file_path)
    duration = int(video.duration)
    if duration < chunk_size:
        with open(file_path, "rb") as audio_file:
            response = openai.Audio.transcribe("whisper-1", audio_file)
            transcript = response["text"]
        return transcript
    video_chunks = split_video(file_path, duration, chunk_size)
    transcript = ""
    for i, chunk in enumerate(video_chunks):
        temp_file = f"temp_chunk_{i}.{ext}"
        chunk.audio.write_audiofile(temp_file)
        with open(temp_file, "rb") as audio_file:
            response = openai.Audio.transcribe("whisper-1", audio_file)
            chunk_transcript = response["text"]
        transcript += chunk_transcript
        os.remove(temp_file)
    return transcript

def download_video(url, private=False, ext="mp3"):
    cookies_option = "--cookies-from-browser chrome" if private else ""
    ext_option = f"-x --audio-format {ext}" if ext == "mp3" else "--merge-output-format mp4"
    command = f"yt-dlp {cookies_option} -o \"video.%(ext)s\" {ext_option} {url}"
    subprocess.run(command, shell=True, check=True)

def gpt_summary(text, max_chunk_tokens=1948):
    tokens = count_tokens(text)
    num_chunks = (tokens + max_chunk_tokens - 1) // max_chunk_tokens
    chunk_size = len(text) // num_chunks
    if chunk_size == 0:
        chunks = [text]
    else:
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
    summary = ""
    for idx, chunk in enumerate(chunks):
        if idx != len(chunks) - 1:
            prompt = """
            Your task is to summarize the text at least 500 words, and retain the keyword like book title or terms. Reply in traditional Chinese. The text is this:        
            %s
            """ % (summary+chunk)
        else:
            prompt = """
Your output should use the following template:
### Summary

### Facts
- Bulletpoint

Your task is to start with a short summary and Summarize related sentences into the same bullet points at least 600 words. Remember retain the keyword like book title or terms. Reply in traditional chinese. The text is this:
            %s
            """ % (summary+chunk)
        print(count_tokens(prompt))
        prompt_tokens = count_tokens(prompt)
        try :
            response = openai.ChatCompletion.create(
                max_tokens=(4000-prompt_tokens),
                top_p=0.7,
                temperature=0.7,
                model="gpt-3.5-turbo",
                messages=[{"role":"user","content":prompt}]
            )
            summary = response.choices[0].message.content
        except:
            response = openai.ChatCompletion.create(
                max_tokens=(3500-prompt_tokens),
                top_p=0.7,
                temperature=0.7,
                model="gpt-3.5-turbo",
                messages=[{"role":"user","content":prompt}]
            )
        summary = response.choices[0].message.content
    return summary

def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("search", help="search command")
    parser.add_argument("-p", '--private', help="Use this flag if the video is private", action='store_true', default=False)
    args = parser.parse_args()
    if args.search == "search":
        while True:
            url = input("Enter the youtube url: ")
            if url == "exit":
                break
            temp_file = f"video.mp4"
            os.remove(temp_file) if os.path.exists(temp_file) else None
            download_video(url, args.private, "mp4")
            text = gpt_large_file_transcript(temp_file)
            summary = gpt_summary(text)
            print(summary)
            parser.exit(0)
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
                            if callback.last_sound_time is not None and (datetime.now() - callback.last_sound_time).total_seconds() > 1:
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