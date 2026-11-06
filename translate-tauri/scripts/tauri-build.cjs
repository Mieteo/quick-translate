// Gọi trực tiếp native tauri CLI, tránh lỗi argv của wrapper trong môi trường embed.
// Tắt tạm createUpdaterArtifacts vì máy này thiếu TAURI_SIGNING_PRIVATE_KEY —
// bản cài vẫn tạo đầy đủ, chỉ không sinh file .sig phục vụ auto-update.
const path = require('path');
process.chdir(path.join(__dirname, '..'));
const { run, logError } = require('@tauri-apps/cli');
run(
  ['build', '--config', JSON.stringify({ bundle: { createUpdaterArtifacts: false } })],
  'tauri'
).catch((e) => { logError(e); process.exit(1); });
