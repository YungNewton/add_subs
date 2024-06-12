import os
import re
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
from io import BytesIO

app = Flask(__name__)
CORS(app)

def parse_srt(srt_content):
    """
    Parse SRT content to extract timestamps and text.

    :param srt_content: str - Content of the SRT file.
    :return: list of tuples - List of (start_time, end_time, text) tuples.
    """
    subtitles = []  # Initialize the subtitles list
    pattern = re.compile(r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})')
    lines = srt_content.splitlines()
    text = ""
    for line in lines:
        line = line.strip()
        matches = pattern.findall(line)
        if matches:
            if text:
                subtitles.append((start_time, end_time, text))
            start_time = matches[0][0]
            end_time = matches[0][1]
            text = ""
        elif line and not line.isdigit():
            text += " " + line if text else line
    if text:  # Append the last subtitle
        subtitles.append((start_time, end_time, text))
    return subtitles

def srt_time_to_seconds(srt_time):
    """
    Convert SRT time format to seconds.

    :param srt_time: str - Time string in SRT format (H:M:S,mmm).
    :return: float - Time in seconds.
    """
    parts = srt_time.split(":")
    h = int(parts[0])
    m = int(parts[1])
    s_ms = parts[2].split(",")
    s = int(s_ms[0])
    ms = int(s_ms[1])

    total_seconds = h * 3600 + m * 60 + s + ms / 1000.0
    return total_seconds

def generator(txt):
    """
    Create a styled TextClip for each subtitle text.

    :param txt: str - The subtitle text.
    :return: TextClip - The styled text clip.
    """
    max_width = 600  # Maximum width for the text box

    # Create the text clip with desired font, size, color, and stroke
    txt_clip = TextClip(
        txt, 
        font='Arial-Bold',      # Font family
        fontsize=36,            # Font size
        color='white',          # Text color
        stroke_color='black',   # Stroke color
        stroke_width=0.5        # Stroke width
    )
    
    # Adjust the width to not exceed max_width and wrap text if necessary
    if txt_clip.w > max_width:
        txt_clip = TextClip(
            txt, 
            font='Arial-Bold', 
            fontsize=36, 
            color='white', 
            stroke_color='black', 
            stroke_width=0.5, 
            method='caption', 
            size=(max_width, None), 
            align='center'
        )
    
    # Add background color with padding
    txt_clip = txt_clip.on_color(
        size=(650, 120),                      # Fixed size of the background
        color=(50, 50, 50),                   # Background color (dark grey)
        pos='center'                          # Center the text within the background
    )
    
    # Position the text clip at the bottom center
    return txt_clip.margin(bottom=50, opacity=0).set_position(("center", "bottom"))

def add_subtitles_to_video(video_content, srt_content):
    """
    Add subtitles to a video using the timestamps and text from an SRT file.

    :param video_content: bytes - Content of the input video file.
    :param srt_content: str - Content of the SRT file.
    :return: bytes - Content of the video file with subtitles.
    """
    video_path = 'temp_video.mp4'
    with open(video_path, 'wb') as f:
        f.write(video_content)
        
    video = VideoFileClip(video_path)
    audio = video.audio  # Extract the audio from the original video
    subtitles = parse_srt(srt_content)

    subtitle_clips = []
    for start_time, end_time, text in subtitles:
        start = srt_time_to_seconds(start_time)
        end = srt_time_to_seconds(end_time)
        txt_clip = generator(text).set_start(start).set_duration(end - start)
        subtitle_clips.append(txt_clip)

    result = CompositeVideoClip([video] + subtitle_clips)
    result = result.set_audio(audio)

    output_buffer = BytesIO()
    result.write_videofile(output_buffer, codec='libx264', fps=video.fps, audio_codec='aac')
    output_buffer.seek(0)

    os.remove(video_path)
    
    return output_buffer.read()

@app.route('/add_subtitles', methods=['POST'])
def add_subtitles():
    if 'video' not in request.files or 'srt' not in request.files:
        return jsonify({"error": "No video or SRT file part"}), 400
    
    video_file = request.files['video']
    srt_file = request.files['srt']

    if video_file.filename == '' or srt_file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    video_content = video_file.read()
    srt_content = srt_file.read().decode('utf-8')

    output_video_content = add_subtitles_to_video(video_content, srt_content)
    
    return send_file(BytesIO(output_video_content), as_attachment=True, attachment_filename='subtitled_video.mp4', mimetype='video/mp4')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)
