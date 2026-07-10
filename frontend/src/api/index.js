import axios from "axios";

const api = axios.create({ baseURL: "/api", timeout: 30000 });

export function fetchDashboard() { return api.get("/dashboard/summary").then(r => r.data); }
export function fetchStudents() { return api.get("/students").then(r => r.data); }
export function fetchStudent(id) { return api.get(`/students/${id}`).then(r => r.data); }
export function fetchRecentEmotions(studentId, limit = 20) {
  return api.get("/emotions/recent", { params: { student_id: studentId, limit } }).then(r => r.data);
}
export function fetchEmotionTimeline(studentId, date) {
  return api.get("/emotions/timeline", { params: { student_id: studentId, date } }).then(r => r.data);
}
export function fetchAlerts(severity, acknowledged) {
  return api.get("/alerts", { params: { severity, acknowledged } }).then(r => r.data);
}
export function acknowledgeAlert(id) { return api.patch(`/alerts/${id}/acknowledge`).then(r => r.data); }
export function fetchDailyReport(studentId, date) {
  return api.get("/reports/daily", { params: { student_id: studentId, date } }).then(r => r.data);
}
export function triggerInner() { return api.post("/agent/trigger/inner").then(r => r.data); }
export function triggerOuter() { return api.post("/agent/trigger/outer").then(r => r.data); }
export function uploadVideo(formData) {
  return api.post("/upload/video", formData, { headers: { "Content-Type": "multipart/form-data" } }).then(r => r.data);
}
export default api;
