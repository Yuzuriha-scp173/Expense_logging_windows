const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("daybook", {
  platform: process.platform,
});
