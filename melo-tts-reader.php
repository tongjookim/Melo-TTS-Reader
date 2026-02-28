<?php
/**
 * Plugin Name: Melo TTS Post Reader
 * Plugin URI: https://www.swn.kr
 * Description: WordPress 포스트를 음성으로 변환해주는 Melo TTS 기반 플러그인
 * Version: 1.0.0
 * Author: The Suwan News Company
 * License: GPL v2 or later
 */

if (!defined('ABSPATH')) {
    exit;
}

class MeloTTS_Reader {
    private $api_endpoint;
    
    public function __construct() {
        $this->api_endpoint = get_option('melo_tts_api_endpoint', 'http://localhost:5000');
        
        add_action('wp_enqueue_scripts', array($this, 'enqueue_scripts'));
        add_filter('the_content', array($this, 'add_audio_player'));
        add_action('wp_ajax_generate_tts', array($this, 'generate_tts'));
        add_action('wp_ajax_nopriv_generate_tts', array($this, 'generate_tts'));
        add_action('admin_menu', array($this, 'add_admin_menu'));
        add_action('admin_init', array($this, 'register_settings'));
    }
    
    public function enqueue_scripts() {
        if (is_single()) {
            wp_enqueue_style('melo-tts-style', plugins_url('css/style.css', __FILE__));
            wp_enqueue_script('melo-tts-script', plugins_url('js/script.js', __FILE__), array('jquery'), '1.0.0', true);
            wp_localize_script('melo-tts-script', 'meloTTS', array(
                'ajax_url' => admin_url('admin-ajax.php'),
                'nonce' => wp_create_nonce('melo_tts_nonce'),
                'post_id' => get_the_ID()
            ));
        }
    }
    
    public function add_audio_player($content) {
        if (is_single() && in_the_loop() && is_main_query()) {
            $player_html = '
            <div class="melo-tts-container">
                <button id="melo-tts-play" class="melo-tts-button">
                    <span class="play-icon">▶</span> 포스트 듣기
                </button>
                <div id="melo-tts-player" style="display:none;">
                    <audio id="melo-tts-audio" controls></audio>
                    <div class="melo-tts-loading">음성을 생성하는 중...</div>
                </div>
            </div>';
            
            return $player_html . $content;
        }
        return $content;
    }
    
    public function generate_tts() {
        check_ajax_referer('melo_tts_nonce', 'nonce');
        
        $post_id = intval($_POST['post_id']);
        $post = get_post($post_id);
        
        if (!$post) {
            wp_send_json_error('포스트를 찾을 수 없습니다.');
            return;
        }
        
        // 캐시 확인
        $cached_audio = get_post_meta($post_id, '_melo_tts_audio_url', true);
        if ($cached_audio && file_exists(ABSPATH . parse_url($cached_audio, PHP_URL_PATH))) {
            wp_send_json_success(array('audio_url' => $cached_audio));
            return;
        }
        
        // 포스트 내용 정리
        $content = wp_strip_all_tags($post->post_content);
        $content = preg_replace('/\s+/', ' ', $content);
        $text = $post->post_title . '. ' . $content;
        
        // Melo TTS API 호출
        $response = wp_remote_post($this->api_endpoint . '/tts', array(
            'body' => json_encode(array(
                'text' => substr($text, 0, 5000),
                'language' => get_option('melo_tts_language', 'KR'),
                'speaker' => get_option('melo_tts_speaker', 'KR')
            )),
            'headers' => array('Content-Type' => 'application/json'),
            'timeout' => 60
        ));
        
        if (is_wp_error($response)) {
            wp_send_json_error('TTS 생성 실패: ' . $response->get_error_message());
            return;
        }
        
        $body = wp_remote_retrieve_body($response);
        $upload_dir = wp_upload_dir();
        $filename = 'melo-tts-' . $post_id . '-' . time() . '.wav';
        $file_path = $upload_dir['path'] . '/' . $filename;
        
        file_put_contents($file_path, $body);
        
        $audio_url = $upload_dir['url'] . '/' . $filename;
        update_post_meta($post_id, '_melo_tts_audio_url', $audio_url);
        
        wp_send_json_success(array('audio_url' => $audio_url));
    }
    
    public function add_admin_menu() {
        add_options_page(
            'Melo TTS 설정',
            'Melo TTS',
            'manage_options',
            'melo-tts-settings',
            array($this, 'settings_page')
        );
    }
    
    public function register_settings() {
        register_setting('melo_tts_options', 'melo_tts_api_endpoint');
        register_setting('melo_tts_options', 'melo_tts_language');
        register_setting('melo_tts_options', 'melo_tts_speaker');
    }
    
    public function settings_page() {
        ?>
        <div class="wrap">
            <h1>Melo TTS 설정</h1>
            <form method="post" action="options.php">
                <?php settings_fields('melo_tts_options'); ?>
                <table class="form-table">
                    <tr>
                        <th scope="row">API 엔드포인트</th>
                        <td>
                            <input type="text" name="melo_tts_api_endpoint" 
                                   value="<?php echo esc_attr(get_option('melo_tts_api_endpoint', 'http://localhost:5000')); ?>" 
                                   class="regular-text">
                            <p class="description">Melo TTS API 서버 주소</p>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">언어</th>
                        <td>
                            <select name="melo_tts_language">
                                <option value="KR" <?php selected(get_option('melo_tts_language'), 'KR'); ?>>한국어</option>
                                <option value="EN" <?php selected(get_option('melo_tts_language'), 'EN'); ?>>English</option>
                                <option value="ZH" <?php selected(get_option('melo_tts_language'), 'ZH'); ?>>中文</option>
                            </select>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">스피커</th>
                        <td>
                            <select name="melo_tts_speaker">
                                <option value="KR" <?php selected(get_option('melo_tts_speaker'), 'KR'); ?>>기본</option>
                            </select>
                        </td>
                    </tr>
                </table>
                <?php submit_button(); ?>
            </form>
        </div>
        <?php
    }
}

// 플러그인 초기화
function melo_tts_init() {
    new MeloTTS_Reader();
}
add_action('plugins_loaded', 'melo_tts_init');