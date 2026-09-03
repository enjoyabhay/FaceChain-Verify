require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config({ path: require("path").join(__dirname, "..", ".env") });
// Use the solc-js/wasm compiler instead of a native platform binary. Some
// networks (corporate proxies in particular) block direct .exe downloads,
// which breaks Hardhat's default native-binary compiler fetch on Windows;
// wasm downloads as a plain .js file and works everywhere. See README.
require("./scripts/force-wasm-solc.cjs");

const AMOY_RPC_URL = process.env.AMOY_RPC_URL || "";
const CHAIN_PRIVATE_KEY = process.env.CHAIN_PRIVATE_KEY || "";

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: "0.8.20",
  networks: {
    localhost: {
      url: "http://127.0.0.1:8545",
    },
    amoy: {
      url: AMOY_RPC_URL || "https://rpc-amoy.polygon.technology",
      accounts: CHAIN_PRIVATE_KEY ? [CHAIN_PRIVATE_KEY] : [],
      chainId: 80002,
    },
  },
};
