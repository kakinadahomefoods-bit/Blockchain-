// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title AttendanceLedger
 * @notice Classroom demonstration contract. Only authorized faculty can write.
 *         Stores keyed pseudonyms (bytes32), NEVER faces or student names.
 *         Original events are retained; corrections are separately flagged.
 */
contract AttendanceLedger {
    address public owner;
    mapping(address => bool) public faculty;
    mapping(bytes32 => bool) public sessionExists;
    mapping(bytes32 => bool) public sessionClosed;
    mapping(bytes32 => mapping(bytes32 => bool)) public present;
    mapping(bytes32 => mapping(bytes32 => bool)) public flagged;

    event FacultyChanged(address indexed account, bool allowed);
    event SessionCreated(bytes32 indexed sessionId, address indexed by, uint256 timestamp);
    event SessionClosed(bytes32 indexed sessionId, address indexed by, uint256 timestamp);
    event AttendanceMarked(bytes32 indexed sessionId, bytes32 indexed studentId, address indexed by, uint256 timestamp);
    event AttendanceFlagged(bytes32 indexed sessionId, bytes32 indexed studentId, address indexed by, bytes32 reasonHash, uint256 timestamp);
    event ManualAttendanceMarked(bytes32 indexed sessionId, bytes32 indexed studentId, address indexed by, bytes32 reasonHash, uint256 timestamp);

    constructor() {
        owner = msg.sender;
        faculty[msg.sender] = true;
        emit FacultyChanged(msg.sender, true);
    }

    modifier onlyOwner() { require(msg.sender == owner, "owner only"); _; }
    modifier onlyFaculty() { require(faculty[msg.sender], "faculty only"); _; }
    modifier openSession(bytes32 id) {
        require(sessionExists[id], "unknown session");
        require(!sessionClosed[id], "session closed");
        _;
    }

    function setFaculty(address account, bool allowed) external onlyOwner {
        require(account != address(0), "invalid address");
        faculty[account] = allowed;
        emit FacultyChanged(account, allowed);
    }

    function createSession(bytes32 id) external onlyFaculty {
        require(id != bytes32(0), "invalid id");
        require(!sessionExists[id], "session already exists");
        sessionExists[id] = true;
        emit SessionCreated(id, msg.sender, block.timestamp);
    }

    function closeSession(bytes32 id) external onlyFaculty openSession(id) {
        sessionClosed[id] = true;
        emit SessionClosed(id, msg.sender, block.timestamp);
    }

    function markAttendance(bytes32 sessionId, bytes32 studentId)
        external onlyFaculty openSession(sessionId)
    {
        require(studentId != bytes32(0), "invalid student id");
        require(!present[sessionId][studentId], "duplicate attendance");
        present[sessionId][studentId] = true;
        emit AttendanceMarked(sessionId, studentId, msg.sender, block.timestamp);
    }

    // Explicit faculty-authorized fallback. The chain distinguishes a manual
    // override from a biometric match. Never silently claim face verification.
    function manualMarkAttendance(bytes32 sessionId, bytes32 studentId, bytes32 reasonHash)
        external onlyFaculty openSession(sessionId)
    {
        require(studentId != bytes32(0), "invalid student id");
        require(reasonHash != bytes32(0), "reason required");
        require(!present[sessionId][studentId], "duplicate attendance");
        present[sessionId][studentId] = true;
        emit ManualAttendanceMarked(sessionId, studentId, msg.sender, reasonHash, block.timestamp);
    }

    function flagAttendance(bytes32 sessionId, bytes32 studentId, bytes32 reasonHash)
        external onlyFaculty openSession(sessionId)
    {
        require(present[sessionId][studentId], "no attendance record");
        require(!flagged[sessionId][studentId], "already flagged");
        require(reasonHash != bytes32(0), "reason required");
        flagged[sessionId][studentId] = true;
        emit AttendanceFlagged(sessionId, studentId, msg.sender, reasonHash, block.timestamp);
    }
}
