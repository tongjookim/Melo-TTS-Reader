from flask import Flask, request, send_file
from flask_cors import CORS
from melo.api import TTS
import io
import tempfile
import os
import re

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

def normalize_text(text, language):
    if language != 'KR':
        return text

    # 1. 영문 알파벳을 한글 발음으로 변환 (OECD -> 오이씨디)
    eng_dict = {
        'A': '에이', 'B': '비', 'C': '씨', 'D': '디', 'E': '이', 'F': '에프', 'G': '지',
        'H': '에이치', 'I': '아이', 'J': '제이', 'K': '케이', 'L': '엘', 'M': '엠',
        'N': '엔', 'O': '오', 'P': '피', 'Q': '큐', 'R': '알', 'S': '에스', 'T': '티',
        'U': '유', 'V': '브이', 'W': '더블유', 'X': '엑스', 'Y': '와이', 'Z': '제트'
    }
    
    def replace_eng(match):
        word = match.group(0).upper()
        return "".join([eng_dict.get(char, char) for char in word])
        
    text = re.sub(r'[a-zA-Z]+', replace_eng, text)

    # 2. 숫자를 한국어 단위로 변환 (3000 -> 삼천)
    def num_to_kr(match):
        num_str = match.group(0)
        units = ['', '십', '백', '천']
        big_units = ['', '만', '억', '조', '경']
        kr_nums = {'1':'일', '2':'이', '3':'삼', '4':'사', '5':'오', '6':'육', '7':'칠', '8':'팔', '9':'구', '0':''}
        
        result = []
        length = len(num_str)
        for i, digit in enumerate(num_str):
            if digit != '0':
                num_char = kr_nums[digit]
                unit_char = units[(length - i - 1) % 4]
                result.append(num_char + unit_char)
            
            if (length - i - 1) % 4 == 0 and (length - i - 1) > 0:
                if sum([int(d) for d in num_str[max(0, i-3):i+1]]) > 0:
                    result.append(big_units[(length - i - 1) // 4])
                    
        return "".join(result) if result else "영"

    text = re.sub(r'\d+', num_to_kr, text)

    # 3. 완벽한 특수문자 제거 (한글, 영문, 숫자, 기본 구두점만 남김)
    text = re.sub(r'[^가-힣a-zA-Z0-9\s\.\,\?\!]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

@app.route('/tts', methods=['POST'])
def generate_tts():
    try:
        data = request.get_json()
        raw_text = data.get('text', '')
        language = data.get('language', 'KR')
        speaker = data.get('speaker', 'KR')
        
        if not raw_text:
            return {'error': 'Text is required'}, 400
        
        if language not in models:
            return {'error': 'Invalid language'}, 400
        
        # 텍스트 정규화 적용
        text = normalize_text(raw_text, language)
        
        model = models[language]
        speaker_dict = speaker_ids[language]
        
        # HParams .get() 에러 방지용 안전한 호출 방식
        if speaker in speaker_dict.keys():
            speaker_id = speaker_dict[speaker]
        else:
            first_key = list(speaker_dict.keys())[0]
            speaker_id = speaker_dict[first_key]

        # ========================================================
        # 메모리 초과(OOM) 방지를 위한 텍스트 쪼개기(Chunking) 로직
        # ========================================================
        raw_sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        temp_str = ""
        
        for sentence in raw_sentences:
            if not sentence.strip(): continue
            temp_str += sentence + " "
            # 약 200자(3~4문장) 단위로 안전하게 자르기
            if len(temp_str) > 200:
                chunks.append(temp_str.strip())
                temp_str = ""
        if temp_str.strip():
            chunks.append(temp_str.strip())
            
        if not chunks:
            chunks = [text]

        chunk_files = []
        final_tmp_path = None
        
        try:
            # 1. 쪼개진 텍스트 조각들을 순서대로 짧은 음성 파일로 생성
            for chunk in chunks:
                chunk_tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                model.tts_to_file(chunk, speaker_id, chunk_tmp.name, speed=1.0)
                chunk_files.append(chunk_tmp.name)
            
            # 2. 생성된 짧은 음성 파일들을 하나로 병합
            final_tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            final_tmp_path = final_tmp.name
            
            data_frames = []
            for w_path in chunk_files:
                with wave.open(w_path, 'rb') as w:
                    data_frames.append([w.getparams(), w.readframes(w.getnframes())])
            
            with wave.open(final_tmp_path, 'wb') as output:
                output.setparams(data_frames[0][0])
                for i in range(len(data_frames)):
                    output.writeframes(data_frames[i][1])
            
            # 3. 완성된 긴 오디오를 전송용 메모리에 담기
            with open(final_tmp_path, 'rb') as f:
                audio_data = io.BytesIO(f.read())
                
        finally:
            # 4. 사용이 끝난 임시 조각 파일들 즉시 청소 (용량 낭비 방지)
            for w_path in chunk_files:
                if os.path.exists(w_path):
                    os.remove(w_path)
            if final_tmp_path and os.path.exists(final_tmp_path):
                os.remove(final_tmp_path)
        
        return send_file(
            audio_data,
            mimetype='audio/wav',
            as_attachment=True,
            download_name='tts_output.wav'
        )
    
    except Exception as e:
        return {'error': str(e)}, 500

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
