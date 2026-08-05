const path = require("path");
module.exports = {
  uiPort: 1880,
  uiHost: "127.0.0.1",
  flowFile: "flows.json",
  httpAdminRoot: "/red",
  httpNodeRoot: "/",
  httpStatic: path.join(__dirname, "public"),
  httpStaticRoot: "/motionedge",
  credentialSecret: false,
  editorTheme: { projects: { enabled: false } },
  functionGlobalContext: {},
  logging: { console: { level: "info", metrics: false, audit: false } }
};
