# Audio Recorder with OpenAI GPT Transcription

This repository contains a Python script for recording audio and using OpenAI's GPT transcription service to transcribe the recorded audio.

## Installation

1. Clone the repository to your local machine.
2. Install the required libraries using pip:
   ```bash
   python -m venv venv
   ```
   ```bash
   . venv/bin/activate
   ```
   ```bash
   pip install -r requirements.txt
   ```
3. Create a file named .env in the project directory and add your OpenAI API key as API_KEY=<your_api_key>
   ```bash
   cp .env.example .env
   ```

## Usage

Run the script using the following command:

```bash
python rec_unlimited.py [-l] [-d DEVICE] [-r SAMPLERATE] [-c CHANNELS] [-s SUBTYPE] [-t THRESHOLD]
```

Arguments:

- -l, --list-devices: Show list of available audio devices and exit.
- -d DEVICE: Input device (numeric ID or substring).
- -r SAMPLERATE: Sampling rate.
- -c CHANNELS: Number of input channels.
- -s SUBTYPE: Sound file subtype (e.g. "PCM_24").
- -t THRESHOLD: RMS threshold for detecting sound (default: 0.01).

When the script is running, use the following commands:

- Press s to start recording.
- Press Ctrl+C to stop recording.
- Press s again to start recording a new audio file.
- Press q to quit the program.
  Recorded audio files will be saved in the record directory in the project directory.

The recorded audio files will be automatically transcribed using OpenAI's GPT transcription service. The transcribed text will be printed to the console.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
