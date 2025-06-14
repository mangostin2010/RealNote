import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, send_file, abort
from werkzeug.utils import secure_filename
import sys
import markdown
import demo
import ffmpeg
from flask import session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import re

app = Flask(__name__)
app.secret_key = 'holyshit'
DOCS_DIR = 'docs'
UPLOAD_DIR = 'uploads'
os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

USERS_FILE = 'users.json'

# Markdown 필터 추가
@app.template_filter('markdown')
def render_markdown(text):
    return markdown.markdown(text)

def get_doc_path(doc_id):
    username = session.get('username')
    if username:
        user_docs_dir = os.path.join(DOCS_DIR, username)
        os.makedirs(user_docs_dir, exist_ok=True)
        return os.path.join(user_docs_dir, f"{doc_id}.md")
    return os.path.join(DOCS_DIR, f"{doc_id}.md")  # 로그인하지 않은 경우 기본 경로 사용

def load_users():
    import json
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(users):
    import json
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # 사용자 이름 유효성 검사 (영문, 숫자 조합 4-20자)
        if not re.match(r'^[a-zA-Z0-9]{4,20}$', username):
            flash('사용자 이름은 영문, 숫자 조합으로 4-20자 이내로 입력해주세요.')
            return render_template('register.html')

        # 비밀번호 길이 검사 (8자 이상)
        if len(password) < 8:
            flash('비밀번호는 8자 이상이어야 합니다.')
            return render_template('register.html')

        # 비밀번호 일치 확인 (프론트엔드에서도 확인하지만 백엔드에서도 확인)
        if password != confirm_password:
            flash('비밀번호가 일치하지 않습니다.')
            return render_template('register.html')
        
        users = load_users()
        if username in users:
            flash('이미 존재하는 사용자입니다.')
        else:
            users[username] = generate_password_hash(password)
            save_users(users)
            flash('회원가입 성공! 로그인 해주세요.')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()
        if username in users and check_password_hash(users[username], password):
            session['username'] = username
            return redirect(url_for('home'))
        else:
            flash('로그인 실패: 아이디 또는 비밀번호가 틀렸습니다.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('로그아웃 되었습니다.')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def home():
    username = session['username']
    user_docs_dir = os.path.join(DOCS_DIR, username)
    os.makedirs(user_docs_dir, exist_ok=True)
    docs = [f[:-3] for f in os.listdir(user_docs_dir) if f.endswith('.md')]
    return render_template('index.html', docs=docs)

@app.route('/share/<doc_id>')
def share_doc(doc_id):
    """공유된 문서를 읽기 전용으로 보여주는 뷰"""
    doc_path = get_doc_path(doc_id)
    owner = None

    if not os.path.exists(doc_path):
        # 로그인하지 않은 경우 모든 사용자 폴더에서 문서 탐색
        found = False
        for user_folder in os.listdir(DOCS_DIR):
            user_docs_dir = os.path.join(DOCS_DIR, user_folder)
            if os.path.isdir(user_docs_dir):
                candidate = os.path.join(user_docs_dir, f"{doc_id}.md")
                if os.path.exists(candidate):
                    doc_path = candidate
                    owner = user_folder
                    found = True
                    break
        if not found:
            abort(404)
    else:
        # 로그인한 경우 소유자 정보
        if 'username' in session:
            owner = session['username']
        else:
            # 경로에서 사용자 이름 추출 시도
            path_parts = doc_path.split(os.sep)
            if len(path_parts) > 2 and path_parts[-2] != DOCS_DIR:
                owner = path_parts[-2]

    with open(doc_path, 'r', encoding='utf-8') as f:
        content = f.read()

    return render_template('share.html', doc_id=doc_id, content=content, owner=owner)

@app.route('/doc/<doc_id>', methods=['GET', 'POST'])
@login_required
def edit_doc(doc_id):
    doc_path = get_doc_path(doc_id)
    if request.method == 'POST':
        content = request.form['content']
        # 줄바꿈 변환 없이 그대로 저장
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return redirect(url_for('edit_doc', doc_id=doc_id))
    else:
        if os.path.exists(doc_path):
            with open(doc_path, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            content = ''
        return render_template('editor.html', doc_id=doc_id, content=content)

@app.route('/doc/<doc_id>/raw')
@login_required
def raw_doc(doc_id):
    doc_path = get_doc_path(doc_id)
    if not os.path.exists(doc_path):
        abort(404)
    return send_file(
        doc_path,
        as_attachment=True,
        download_name=f"{doc_id}.md",
        mimetype='text/markdown'
    )

@app.route('/api/doc/<doc_id>', methods=['DELETE'])
@login_required
def delete_doc(doc_id):
    doc_path = get_doc_path(doc_id)
    if os.path.exists(doc_path):
        os.remove(doc_path)
        return jsonify({'success': True, 'message': '문서가 삭제되었습니다.'})
    else:
        return jsonify({'success': False, 'message': '문서를 찾을 수 없습니다.'}), 404
        
@app.route('/api/docs', methods=['GET'])
@login_required
def api_docs():
    """저장된 모든 노트(문서) ID 목록 반환"""
    username = session['username']
    user_docs_dir = os.path.join(DOCS_DIR, username)
    os.makedirs(user_docs_dir, exist_ok=True)
    docs = [f[:-3] for f in os.listdir(user_docs_dir) if f.endswith('.md')]
    return jsonify({'docs': docs})

@app.route('/api/doc/<doc_id>', methods=['HEAD'])
def api_doc_head(doc_id):
    """특정 노트(문서) 존재 여부 확인 (HEAD 요청)"""
    doc_path = get_doc_path(doc_id)
    if os.path.exists(doc_path):
        return '', 200
    else:
        return '', 404

@app.route('/api/doc/<doc_id>', methods=['GET'])
def api_doc_get(doc_id):
    """특정 노트(문서) 내용 반환 (API)"""
    doc_path = get_doc_path(doc_id)
    if os.path.exists(doc_path):
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'content': content})
    else:
        return jsonify({'content': ''}), 404

@app.route('/api/doc/<doc_id>', methods=['POST'])
@login_required
def api_doc_post(doc_id):
    """특정 노트(문서) 내용 덮어쓰기(생성/수정)"""
    doc_path = get_doc_path(doc_id)
    data = request.get_json()
    content = data.get('content', '')
    with open(doc_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return jsonify({'success': True, 'message': '문서가 저장되었습니다.'})
    
@app.route('/voice_note', methods=['GET', 'POST'])
def voice_note():
    note = None
    error = None
    docs = [f[:-3] for f in os.listdir(DOCS_DIR) if f.endswith('.md')]
    
    if request.method == 'POST':
        is_new = request.form.get('is_new', 'y') == 'y'
        selected_title = request.form.get('selected_note')
        
        if 'audio' not in request.files:
            error = "오디오 파일이 업로드되지 않았습니다."
        else:
            file = request.files['audio']
            if file.filename == '':
                error = "선택된 파일이 없습니다."
            else:
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(app.root_path, 'uploads')
                os.makedirs(upload_folder, exist_ok=True)
                filepath = os.path.join(upload_folder, filename)
                file.save(filepath)

                # 디버깅 메시지 추가
                print(f"파일 저장됨: {filepath}")

                # webm → wav 변환
                wav_path = filepath.rsplit('.', 1)[0] + '.wav'
                try:
                    # 직접 ffmpeg 명령어 실행으로 변경
                    import subprocess
                    result = subprocess.run(
                        ['ffmpeg', '-i', filepath, '-y', wav_path], 
                        capture_output=True, 
                        text=True
                    )
                    if result.returncode != 0:
                        raise Exception(f"FFmpeg 오류: {result.stderr}")
                        
                    print(f"변환 성공: {wav_path}")
                    text = demo.transcribe_audio(wav_path)
                    print(f"STT 결과: {text}")
                    os.remove(wav_path)
                except Exception as e:
                    error = f"webm→wav 변환 실패: {e}"
                    print(f"변환 오류: {e}")
                    text = None

                # 업로드된 원본 파일 삭제
                if os.path.exists(filepath):
                    os.remove(filepath)
                    
                if not text and not error:
                    error = "STT 실패"
                    print("STT 실패")
                elif text:
                    try:
                        if is_new:
                            # 새 노트 생성
                            note = demo.write_note(text)
                            print(f"노트 생성 결과: {note}")
                            
                            # 노트를 실제 파일로 저장
                            if note and 'title' in note and 'summary' in note:
                                doc_path = get_doc_path(note['title'])
                                
                                # summary가 리스트인 경우 문자열로 변환
                                if isinstance(note['summary'], list):
                                    content = '\n'.join(note['summary'])
                                else:
                                    content = note['summary']
                                    
                                with open(doc_path, 'w', encoding='utf-8') as f:
                                    f.write(content)
                                print(f"노트 파일 저장됨: {doc_path}")
                        else:
                            # 기존 노트에 추가
                            if not selected_title:
                                error = "선택된 노트가 없습니다."
                            else:
                                # 기존 노트 내용 가져오기
                                doc_path = get_doc_path(selected_title)
                                if os.path.exists(doc_path):
                                    with open(doc_path, 'r', encoding='utf-8') as f:
                                        prev_content = f.read()
                                    
                                    # 기존 내용과 새 텍스트 합치기
                                    combined_text = f"{prev_content}\n\n{text}"
                                    note = demo.write_note(combined_text)
                                    
                                    # 노트 저장
                                    if note and 'summary' in note:
                                        if isinstance(note['summary'], list):
                                            content = '\n'.join(note['summary'])
                                        else:
                                            content = note['summary']
                                        
                                        with open(doc_path, 'w', encoding='utf-8') as f:
                                            f.write(content)
                                        
                                        # 제목은 기존 노트 제목 유지
                                        note['title'] = selected_title
                                        print(f"노트 업데이트됨: {doc_path}")
                                else:
                                    error = "선택한 노트를 찾을 수 없습니다."
                    except Exception as e:
                        error = f"노트 생성 실패: {e}"
                        print(f"노트 생성 오류: {e}")
    
    # 디버깅용 출력
    print(f"렌더링: note={note}, error={error}")
    return render_template('voice_note.html', note=note, error=error, docs=docs)
    
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)