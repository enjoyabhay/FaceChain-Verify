// Forces Hardhat to fetch the solc-js/wasm compiler instead of a native
// platform binary. Required on networks (some corporate proxies included)
// that block direct .exe downloads -- wasm downloads as a plain .js file
// and works everywhere. Loaded by default from hardhat.config.js.
try {
  const {
    CompilerDownloader,
    CompilerPlatform,
  } = require("hardhat/internal/solidity/compiler/downloader");
  CompilerDownloader.getCompilerPlatform = () => CompilerPlatform.WASM;
} catch (err) {
  // If hardhat's internal module path ever changes, just skip the patch --
  // the normal (native binary) download path will be used instead.
}
