import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import requests
import base64
import write
import json
import os

# --- STT 함수 (네가 올린 코드, JSON 포맷으로 결과 요청) ---
url = "https://text.pollinations.ai/openai"
headers = {"Content-Type": "application/json"}

def encode_audio_base64(audio_path):
    try:
        with open(audio_path, "rb") as audio_file:
            return base64.b64encode(audio_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"Error: Audio file not found at {audio_path}")
        return None

def transcribe_audio(audio_path):
    base64_audio = encode_audio_base64(audio_path)
    if not base64_audio:
        return None

    audio_format = audio_path.split('.')[-1].lower()
    supported_formats = ['mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'wav', 'webm']
    if audio_format not in supported_formats:
         print(f"Warning: Potentially unsupported audio format '{audio_format}'. Check API documentation.")

    # LLM에게 JSON 포맷으로 출력하라고 요청
    question = (
        "아래 오디오를 텍스트로 전사해줘. "
        "그리고 반드시 다음과 같은 JSON 형식으로만 출력해: "
        '{"text": "Transcriptions are placed here."}'
    )

    payload = {
        "model": "openai-audio",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {
                        "type": "input_audio",
                        "input_audio": {
                           "data": base64_audio,
                           "format": audio_format
                        }
                    }
                ]
            }
        ],
        "private": True
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        # LLM이 JSON string을 반환한다고 가정
        content = result.get('choices', [{}])[0].get('message', {}).get('content')
        # content가 JSON string이면 파싱
        try:
            json_result = json.loads(content)
            return json_result.get("text")
        except Exception as e:
            print("JSON 파싱 실패, 원본 출력:", content)
            return content
    except requests.exceptions.RequestException as e:
        print(f"Error transcribing audio: {e}")
        return None

# --- 노트 작성 함수 ---
def write_note(text):
    url = "https://text.pollinations.ai/openai"

    system_prompt = """당신의 역할은 입력된 텍스트를 바탕으로 **핵심 내용을 정확하게 요약**하는 것입니다. 아래의 규칙을 반드시 지키세요:

- 요약 결과는 아래 JSON 형식으로 출력해야 합니다:
{
    "title": "Title goes here",
    "summary": "Summarization in markdown goes here"
}
- title에는 텍스트의 주제를 간결하게 작성합니다.
- summary에는 Markdown 형식을 사용하여, 문단이나 문장 단위가 아닌 **핵심 포인트별로 자세하게** 정리합니다.
- 각 핵심 포인트는 Markdown의 리스트(`-`)로 작성하며, 필요하다면 서브 리스트(`  -`)도 활용합니다.
- 불필요한 내용이나 부연 설명은 생략하고, **핵심 정보만** 명확하게 전달합니다.
- **JSON 전체를 출력할 때, 절대로 백틱(```)을 사용하지 마세요.**
- 출력 결과에 코드 블록이나 인라인 코드 등 백틱이 포함되어서는 안 됩니다.
- **입력된 텍스트에 주어진 정보만 요약하며, 주어지지 않은 정보나 추가적인 추론, 상상, 해석은 절대로 작성하지 마세요.**"""

    system_prompt = """당신의 역할은 입력된 텍스트를 바탕으로 **중복 없이, 불필요한 부연 설명이나 모호한 표현 없이, 핵심 정보만을 명확하게 요약**하는 것입니다. 아래의 규칙을 반드시 지키세요:

- 요약 결과는 아래 JSON 형식으로 출력해야 합니다:
{
    "title": "텍스트의 주제를 간결하게 작성",
    "summary": "핵심 포인트를 Markdown 리스트(`-`)로 정리"
}
- title에는 텍스트의 전체 주제를 한 문장 또는 한 단어로 간결하게 작성하세요.
- summary에는 **중복되는 내용이나 불필요한 세부사항, 부연 설명, 모호한 표현(예: '등', '같은 것')을 모두 제거**하고, **핵심 정보만** Markdown 리스트(`-`)로 정리하세요.
- 각 포인트는 **중복 없이, 명확하게** 작성하고, 필요할 때만 서브 리스트(`  -`)를 사용하세요.
- 입력에 없는 정보, 추론, 상상, 해석은 절대 추가하지 마세요.
- **JSON 전체를 출력할 때, 절대로 백틱(```)을 사용하지 마세요.**
- 출력 결과에 코드 블록이나 인라인 코드 등 백틱이 포함되어서는 안 됩니다.

예시
입력: "지금 매우 졸리다. 10시 36분이다. 오늘 4시에 일어나 새벽기도를 갈 예정이다. 학교에 교복을 두고 와서 내일은 새학복을 입고 학교에 가야 한다. 학교에 도착하면 교복으로 갈아입을 것이다. 11시쯤 잠자리에 들고 4시에 일어날 계획이다. 새벽기도 후 학교에서 식사 등 일상 활동을 할 예정이다."

출력:
{
    "title": "내일 일정 및 준비",
    "summary": "- 현재 졸린 상태임\n- 내일 4시에 기상하여 새벽기도에 참석할 예정임\n- 교복을 학교에 두고 와서 새학복을 입고 등교할 계획임\n- 학교 도착 후 교복으로 갈아입을 예정임\n- 새벽기도 후 학교에서 일상 활동을 할 예정임"
}

**반드시 위의 규칙을 지키세요.**
"""

    payload = {
        "model": "openai-large",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "private": True
    }
    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        content = result['choices'][0]['message']['content']
        try:
            json_result = json.loads(content)
            
            # Check if summary is a JSON string and try to parse it
            if isinstance(json_result.get("summary"), str) and json_result.get("summary").strip().startswith("{"):
                try:
                    nested_json = json.loads(json_result["summary"])
                    if isinstance(nested_json, dict) and "title" in nested_json and "summary" in nested_json:
                        return nested_json
                except json.JSONDecodeError:
                    pass  # If nested parsing fails, continue with original result
                    
            return json_result
        except json.JSONDecodeError:
            print("Failed to parse JSON, returning raw content")
            # JSON 파싱 실패 시 딕셔너리 형태로 반환
            return {
                "title": "자동 생성 노트",
                "summary": content
            }
    except requests.exceptions.RequestException as e:
        print(f"Error making POST request: {e}")

# --- 녹음 함수 ---
def record_audio(filename="recorded.wav", sample_rate=16000, channels=1):
    print("녹음을 시작하려면 Enter를 누르세요.")
    input()
    print("녹음 중... (멈추려면 Enter를 누르세요)")
    recording = []
    stream = sd.InputStream(samplerate=sample_rate, channels=channels, dtype='int16')
    stream.start()
    try:
        while True:
            if sd.wait(0.1) is None:  # 0.1초마다 체크
                frames = stream.read(1024)[0]
                recording.append(frames)
            if os.name == 'nt':
                import msvcrt
                if msvcrt.kbhit() and msvcrt.getch() == b'\r':
                    break
            else:
                import sys, select
                if select.select([sys.stdin], [], [], 0)[0]:
                    break
    except KeyboardInterrupt:
        pass
    stream.stop()
    audio = np.concatenate(recording, axis=0)
    wav.write(filename, sample_rate, audio)
    print("녹음 완료!")
    return filename

def list_notes(client):
    """기존 노트 목록을 가져오는 함수"""
    try:
        notes = client.list_docs()
        return notes
    except Exception as e:
        print(f"노트 목록을 불러오는 데 실패했습니다: {e}")
        return []

def read_note_content(client, title):
    """특정 노트의 내용을 가져오는 함수"""
    try:
        return client.read_doc(title)
    except Exception as e:
        print(f"노트 내용을 불러오는 데 실패했습니다: {e}")
        return None
        
if __name__ == "__main__":
    filename = "recorded.wav"
    client = write.MarkdownDocClient("http://localhost:5000")

    print("새로운 노트를 만드시겠습니까? (y/n)")
    is_new = input().strip().lower() == "y"

    if not is_new:
        # 기존 노트 목록 보여주기
        notes = list_notes(client)
        if not notes:
            print("기존 노트가 없습니다. 새로운 노트를 생성합니다.")
            is_new = True
        else:
            print("기존 노트 목록:")
            for idx, note_title in enumerate(notes):
                print(f"{idx+1}. {note_title}")
            print("덧붙일 노트 번호를 입력하세요:")
            try:
                sel = int(input().strip()) - 1
                if sel < 0 or sel >= len(notes):
                    print("잘못된 번호입니다. 새로운 노트를 생성합니다.")
                    is_new = True
                else:
                    selected_title = notes[sel]
                    prev_content = read_note_content(client, selected_title)
            except Exception:
                print("입력 오류. 새로운 노트를 생성합니다.")
                is_new = True

    record_audio(filename)
    print("STT 처리 중...")
    text = transcribe_audio(filename)
    if text:
        print(f"\n📝 인식 결과:\n{text}\n")
    else:
        print("❌ 인식 실패\n")
        os.remove(filename)
        exit(1)

    if is_new:
        note = write_note(text)
        if note is None:
            print("노트 생성에 실패했습니다.")
            os.remove(filename)
            exit(1)
            
        print(note)
        # 노트가 딕셔너리인지 확인
        if isinstance(note, dict) and "title" in note and "summary" in note:
            client.write_doc(note["title"], note["summary"])
        else:
            print("노트 형식이 올바르지 않습니다.")
    else:
        # 기존 노트 내용과 새 텍스트를 합쳐서 맥락 반영 요약
        print("기존 노트 내용을 불러와 새 내용과 합칩니다.")
        combined_text = f"당신은 사용자의 노트를 현재 덮어쓰고 있습니다. 도움이 되는 정보를 바탕으로 노트를 개선하십시오. 다음은 원래 있었던 노트의 내용입니다: \n{prev_content}\n다음은 당신이 사용자의 노트에 새롭게 추가해야 하는 내용입니다:\n{str(text)}"
        note = write_note(combined_text)
        print(note)
        client.write_doc(selected_title, note["summary"])

    os.remove(filename)