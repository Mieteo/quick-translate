// Gọi trực tiếp native tauri CLI, tránh lỗi argv của wrapper trong môi trường embed.
// Tắt tạm createUpdaterArtifacts vì máy này thiếu TAURI_SIGNING_PRIVATE_KEY —
// bản cài vẫn tạo đầy đủ, chỉ không sinh file .sig phục vụ auto-update.
const path = require('path');
process.chdir(path.join(__dirname, '..'));
process.env.TRANSLATE_BUILD_EPOCH = String(Math.floor(Date.now() / 1000));
const { run, logError } = require('@tauri-apps/cli');
run(
  ['build', '--config', JSON.stringify({ bundle: { createUpdaterArtifacts: false } })],
  'tauri'
).catch((e) => { logError(e); process.exit(1); });
