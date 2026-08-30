<template>
  <div class="feedback-widget">
    <button class="feedback-btn" @click="show = true" title="用户反馈">💬</button>
    <div class="feedback-modal" v-if="show" @click.self="show = false">
      <div class="feedback-card">
        <h3>用户反馈</h3>
        <div class="stars">
          <span v-for="i in 5" :key="i" @click="rating = i" :class="{ active: i <= rating }">
            {{ i <= rating ? '★' : '☆' }}
          </span>
        </div>
        <textarea v-model="content" placeholder="请分享您的使用体验或建议..." rows="3"></textarea>
        <div class="actions">
          <button class="btn-cancel" @click="show = false">取消</button>
          <button class="btn-submit" @click="submit" :disabled="submitting">
            {{ submitting ? '提交中...' : '提交反馈' }}
          </button>
        </div>
        <div v-if="done" class="success-msg">✅ 感谢您的反馈！</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import axios from "axios";

const show = ref(false);
const rating = ref(5);
const content = ref("");
const submitting = ref(false);
const done = ref(false);

async function submit() {
  submitting.value = true;
  try {
    await axios.post("/api/admin/feedback", null, {
      params: { rating: rating.value, content: content.value },
    });
    done.value = true;
    setTimeout(() => { show.value = false; done.value = false; content.value = ""; rating.value = 5; }, 1500);
  } catch (e) {
    alert("提交失败，请稍后再试");
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.feedback-widget { position: fixed; bottom: 24px; right: 24px; z-index: 9999; }
.feedback-btn { width: 48px; height: 48px; border-radius: 50%; border: none; background: #4f46e5; color: #fff; font-size: 22px; cursor: pointer; box-shadow: 0 4px 12px rgba(79,70,229,0.4); }
.feedback-modal { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 10000; }
.feedback-card { background: #fff; border-radius: 12px; padding: 32px; width: 380px; max-width: 90vw; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.feedback-card h3 { margin: 0 0 16px; font-size: 18px; }
.stars { margin-bottom: 16px; }
.stars span { font-size: 28px; cursor: pointer; color: #d1d5db; transition: color 0.15s; margin-right: 4px; }
.stars span.active { color: #f59e0b; }
textarea { width: 100%; padding: 10px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 14px; resize: vertical; font-family: inherit; box-sizing: border-box; }
.actions { display: flex; gap: 8px; margin-top: 12px; justify-content: flex-end; }
.btn-cancel { padding: 8px 16px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; cursor: pointer; }
.btn-submit { padding: 8px 16px; border: none; border-radius: 8px; background: #4f46e5; color: #fff; cursor: pointer; }
.btn-submit:disabled { opacity: 0.6; cursor: not-allowed; }
.success-msg { margin-top: 12px; text-align: center; color: #059669; font-weight: 500; }
</style>
