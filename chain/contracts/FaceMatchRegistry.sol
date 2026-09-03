// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title FaceMatchRegistry
/// @notice Anchors a tamper-evident fingerprint of a discovered face-match
/// record on-chain. Only a keccak256 hash + the discovered post's public
/// metadata are stored -- raw biometric data never touches the chain.
contract FaceMatchRegistry {
    struct Record {
        bytes32 dataHash; // keccak256(face image bytes || postUrl || matchedImageUrl || timestamp)
        string postUrl;
        string matchedImageUrl;
        uint256 timestamp;
        address submitter;
    }

    Record[] private records;

    event RecordAdded(
        uint256 indexed recordId,
        bytes32 indexed dataHash,
        address indexed submitter,
        string postUrl
    );

    /// @notice Store a new record. `dataHash` must be computed off-chain by
    /// the caller over the exact bytes they want to anchor.
    function addRecord(
        bytes32 dataHash,
        string calldata postUrl,
        string calldata matchedImageUrl,
        uint256 timestamp
    ) external returns (uint256 recordId) {
        records.push(
            Record({
                dataHash: dataHash,
                postUrl: postUrl,
                matchedImageUrl: matchedImageUrl,
                timestamp: timestamp,
                submitter: msg.sender
            })
        );
        recordId = records.length - 1;
        emit RecordAdded(recordId, dataHash, msg.sender, postUrl);
    }

    function getRecord(
        uint256 recordId
    )
        external
        view
        returns (
            bytes32 dataHash,
            string memory postUrl,
            string memory matchedImageUrl,
            uint256 timestamp,
            address submitter
        )
    {
        require(recordId < records.length, "Record does not exist");
        Record storage r = records[recordId];
        return (r.dataHash, r.postUrl, r.matchedImageUrl, r.timestamp, r.submitter);
    }

    function totalRecords() external view returns (uint256) {
        return records.length;
    }
}
