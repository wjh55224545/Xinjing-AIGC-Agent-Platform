import { defineStore } from "pinia";
import { fetchDashboard, fetchStudents, fetchAlerts } from "../api";

export const useDashboardStore = defineStore("dashboard", {
  state: () => ({
    summary: null,
    students: [],
    alerts: [],
    loading: false,
  }),
  actions: {
    async loadSummary() {
      this.summary = await fetchDashboard();
    },
    async loadStudents() {
      this.students = await fetchStudents();
    },
    async loadAlerts(severity) {
      this.alerts = await fetchAlerts(severity);
    },
  },
});
