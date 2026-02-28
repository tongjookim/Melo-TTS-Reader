from flask import Flask, request, send_file
from flask_cors import CORS
from melo.api import TTS
import io
import tempfile
import os

app = Flask(__name__)
CORS(app)

# Melo TTS 모델 초기화
models = {
    'KR': TTS(language='KR', device='auto'),
    'EN': TTS(language='EN', device='auto'),
    'ZH': TTS(language='ZH', device='auto')
}

speaker_ids = {
    'KR': models['KR'].hps.data.spk2id,
    'EN': models['EN'].hps.data.spk2id,
    'ZH': models['ZH'].hps.data.spk2id
}

@app.route('/tts', methods=['POST'])
def generate_tts():
    try:
        data = request.get_json()
        text = data.get('text', '')
        language = data.get('language', 'KR')
        speaker = data.get('speaker', 'KR')
        
        if not text:
            return {'error': 'Text is required'}, 400
        
        if language not in models:
            return {'error': 'Invalid language'}, 400
        
        # TTS 생성
        model = models[language]
        speaker_id = list(speaker_ids[language].keys())[0]
        
        # 임시 파일에 오디오 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            model.tts_to_file(text, speaker_id, tmp_file.name, speed=1.0)
            tmp_file_path = tmp_file.name
        
        # 오디오 파일 반환
        return send_file(
            tmp_file_path,
            mimetype='audio/wav',
            as_attachment=True,
            download_name='tts_output.wav'
        )
    
    except Exception as e:
        return {'error': str(e)}, 500
    finally:
        # 임시 파일 정리
        if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
            try:
                os.unlink(tmp_file_path)
            except:
                pass

@app.route('/health', methods=['GET'])
def health_check():
    return {'status': 'ok', 'available_languages': list(models.keys())}

@app.route('/speakers/<language>', methods=['GET'])
def get_speakers(language):
    if language not in speaker_ids:
        return {'error': 'Invalid language'}, 400
    
    return {'speakers': speaker_ids[language]}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)