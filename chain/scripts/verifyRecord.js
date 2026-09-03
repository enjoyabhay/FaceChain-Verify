const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const deploymentPath = path.join(__dirname, "..", "deployment.json");
  if (!fs.existsSync(deploymentPath)) {
    throw new Error("No deployment found. Run deploy.js first.");
  }
  const { address } = JSON.parse(fs.readFileSync(deploymentPath, "utf8"));

  const recordId = process.env.RECORD_ID;
  if (recordId === undefined) {
    throw new Error("Missing required env var: RECORD_ID");
  }

  const FaceMatchRegistry = await hre.ethers.getContractFactory("FaceMatchRegistry");
  const contract = FaceMatchRegistry.attach(address);

  const record = await contract.getRecord(recordId);

  console.log(
    JSON.stringify({
      dataHash: record[0],
      postUrl: record[1],
      matchedImageUrl: record[2],
      timestamp: record[3].toString(),
      submitter: record[4],
      contractAddress: address,
      network: hre.network.name,
    })
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
