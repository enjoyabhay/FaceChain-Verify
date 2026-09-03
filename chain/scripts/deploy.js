const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const FaceMatchRegistry = await hre.ethers.getContractFactory("FaceMatchRegistry");
  const contract = await FaceMatchRegistry.deploy();
  await contract.waitForDeployment();
  const address = await contract.getAddress();

  const deployment = {
    network: hre.network.name,
    address,
    deployedAt: new Date().toISOString(),
  };

  fs.writeFileSync(
    path.join(__dirname, "..", "deployment.json"),
    JSON.stringify(deployment, null, 2)
  );

  console.log(JSON.stringify(deployment));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
