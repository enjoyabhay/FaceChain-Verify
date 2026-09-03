const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const deploymentPath = path.join(__dirname, "..", "deployment.json");
  if (!fs.existsSync(deploymentPath)) {
    throw new Error("No deployment found. Run deploy.js first.");
  }
  const { address } = JSON.parse(fs.readFileSync(deploymentPath, "utf8"));

  const dataHash = process.env.DATA_HASH;
  const postUrl = process.env.POST_URL;
  const matchedImageUrl = process.env.MATCHED_IMAGE_URL || "";
  const timestamp = process.env.TIMESTAMP;

  if (!dataHash || !postUrl || !timestamp) {
    throw new Error("Missing required env vars: DATA_HASH, POST_URL, TIMESTAMP");
  }

  const FaceMatchRegistry = await hre.ethers.getContractFactory("FaceMatchRegistry");
  const contract = FaceMatchRegistry.attach(address);

  const tx = await contract.addRecord(dataHash, postUrl, matchedImageUrl, timestamp);
  const receipt = await tx.wait();

  const total = await contract.totalRecords();
  const recordId = total - 1n;

  console.log(
    JSON.stringify({
      txHash: receipt.hash,
      blockNumber: receipt.blockNumber,
      recordId: recordId.toString(),
      contractAddress: address,
      network: hre.network.name,
    })
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
