// js/script.js
jQuery(document).ready(function($) {
    let audioGenerated = false;
    
    $('#melo-tts-play').on('click', function() {
        const button = $(this);
        const player = $('#melo-tts-player');
        const audio = $('#melo-tts-audio')[0];
        const loading = $('.melo-tts-loading');
        
        if (audioGenerated && audio.src) {
            // 이미 생성된 오디오 재생/일시정지
            if (audio.paused) {
                audio.play();
                button.html('<span class="play-icon">⏸</span> 일시정지');
            } else {
                audio.pause();
                button.html('<span class="play-icon">▶</span> 재생');
            }
            return;
        }
        
        // 오디오 생성
        button.prop('disabled', true);
        player.show();
        loading.show();
        
        $.ajax({
            url: meloTTS.ajax_url,
            type: 'POST',
            data: {
                action: 'generate_tts',
                post_id: meloTTS.post_id,
                nonce: meloTTS.nonce
            },
            success: function(response) {
                if (response.success) {
                    audio.src = response.data.audio_url;
                    audio.load();
                    audio.play();
                    audioGenerated = true;
                    loading.hide();
                    button.prop('disabled', false);
                    button.html('<span class="play-icon">⏸</span> 일시정지');
                    
                    // 오디오 이벤트 리스너
                    audio.addEventListener('play', function() {
                        button.html('<span class="play-icon">⏸</span> 일시정지');
                    });
                    
                    audio.addEventListener('pause', function() {
                        button.html('<span class="play-icon">▶</span> 재생');
                    });
                    
                    audio.addEventListener('ended', function() {
                        button.html('<span class="play-icon">▶</span> 다시 듣기');
                    });
                } else {
                    alert('음성 생성 실패: ' + response.data);
                    button.prop('disabled', false);
                    loading.hide();
                }
            },
            error: function() {
                alert('서버 오류가 발생했습니다.');
                button.prop('disabled', false);
                loading.hide();
            }
        });
    });
});