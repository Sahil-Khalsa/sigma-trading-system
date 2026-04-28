const RAW_API = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const API_URL = RAW_API.replace(/\/$/, "");
export const WS_URL = API_URL.replace(/^http/, "ws") + "/ws";
