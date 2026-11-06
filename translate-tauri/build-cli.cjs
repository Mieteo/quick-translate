// Gọi trực tiếp native Tauri CLI, bỏ qua wrapper tauri.js (wrapper đọc argv[0]
// là Kimi.exe nên truyền sai subcommand trong môi trường này).
// Tắt tạm createUpdaterArtifacts khi build local vì không có private key tạo file .sig,
// bản cài NSIS vẫn được tạo đầy đủ.
const path = require('path');
const cli = require(path.join(__dirname, 'node_modules', '@tauri-apps', 'cli', 'main'));

cli.run(['build', '--config', JSON.stringify({ bundle: { createUpdaterArtifacts: false } })], 'tauri')
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err && err.message ? err.message : err);
    process.exit(1);
  });
