#!/usr/bin/env python3

import csv
from pathlib import Path


DEFAULT_ZK_INPUT = Path("RQ1/dataset/testing_log/zookeeper_query_segments_candidates.csv")
DEFAULT_LOG_ROOT = Path("RQ1/dataset/backup/privious_resources/testing_log/sample_500_logs")
DEFAULT_OUTPUT = Path("RQ1/dataset/testing_log/testing_log_semantic_diverse_30_messages.csv")


ZK_SEMANTIC_SPECS = [
    ("test_lifecycle", "STARTING Optional[public void"),
    ("test_harness_port_orchestration", "Test process"),
    ("test_harness_temp_env", "tmpDir ="),
    ("test_harness_config_load", "Reading configuration from"),
    ("distributed_test_setup", "QuorumBase.setup"),
    ("distributed_role_transition", "FOLLOWING - LEADER ELECTION TOOK"),
    ("feature_toggle_or_reconfig_mode", "Dynamic reconfig is disabled"),
    ("test_infra_remote_control", "connecting to addr service:jmx:rmi://"),
    ("auth_policy_signal", "zookeeper.enforce.auth.enabled ="),
    ("auth_success_signal", "Setting authorizedID:"),
    ("fault_or_unexpected_exception", "Unexpected exception, tries="),
    ("state_persistence_write", "Snapshotting:"),
    ("state_persistence_recovery", "Reading snapshot"),
    ("assertion_or_outcome_evidence", "Error count"),
    ("test_specific_oracle_mechanism", "Oracle is set to"),
]


SUPPLEMENT_SPECS = [
    (
        "test_cluster_service_start",
        "hadoop",
        "hadoop/hadoop-yarn-project/hadoop-yarn/hadoop-yarn-applications/hadoop-yarn-services/hadoop-yarn-services-api/target/surefire-reports/org.apache.hadoop.yarn.service.TestCleanupAfterKill-output.txt",
        "Starting up YARN cluster",
    ),
    (
        "test_service_orchestration",
        "hadoop",
        "hadoop/hadoop-common-project/hadoop-registry/target/surefire-reports/org.apache.hadoop.registry.client.impl.TestCuratorService-output.txt",
        "Creating CuratorService",
    ),
    (
        "mini_cluster_startup",
        "hadoop",
        "hadoop/hadoop-hdfs-project/hadoop-hdfs/target/surefire-reports/org.apache.hadoop.hdfs.TestMiniDFSCluster-output.txt",
        "starting cluster: numNameNodes=",
    ),
    (
        "kerberos_test_environment",
        "hadoop",
        "hadoop/hadoop-hdfs-project/hadoop-hdfs/target/surefire-reports/org.apache.hadoop.hdfs.web.TestWebHdfsTokens-output.txt",
        "MiniKdc started.",
    ),
    (
        "keytab_login_success",
        "hadoop",
        "hadoop/hadoop-hdfs-project/hadoop-hdfs-rbf/target/surefire-reports/org.apache.hadoop.fs.contract.router.TestRouterHDFSContractDelegationToken-output.txt",
        "Login successful for user",
    ),
    (
        "web_auth_service_start",
        "hadoop",
        "hadoop/hadoop-hdfs-project/hadoop-hdfs-rbf/target/surefire-reports/org.apache.hadoop.hdfs.server.federation.router.TestRouterMountTableCacheRefreshSecure-output.txt",
        "Starting web server as:",
    ),
    (
        "delegation_token_rotation",
        "hadoop",
        "hadoop/hadoop-yarn-project/hadoop-yarn/hadoop-yarn-client/target/surefire-reports/org.apache.hadoop.yarn.client.TestApplicationClientProtocolOnHA-output.txt",
        "Updating the current master key for generating delegation tokens",
    ),
    (
        "ha_cluster_seed",
        "hadoop",
        "hadoop/hadoop-hdfs-project/hadoop-hdfs/target/surefire-reports/org.apache.hadoop.hdfs.server.namenode.ha.TestBootstrapStandbyWithQJM-output.txt",
        "Set MiniQJMHACluster basePort",
    ),
    (
        "activemq_test_banner",
        "activemq",
        "activemq/activemq-amqp/target/surefire-reports/org.apache.activemq.transport.amqp.JMSClientTest-output.txt",
        "========== start test",
    ),
    (
        "amqp_auth_handshake",
        "activemq",
        "activemq/activemq-amqp/target/surefire-reports/org.apache.activemq.transport.amqp.JMSClientTest-output.txt",
        "SASL [PLAIN} Handshake complete.",
    ),
    (
        "amqp_connection_established",
        "activemq",
        "activemq/activemq-amqp/target/surefire-reports/org.apache.activemq.transport.amqp.JMSClientNioTest-output.txt",
        "connected to server: amqp://",
    ),
    (
        "flow_control_outcome",
        "activemq",
        "activemq/activemq-amqp/target/surefire-reports/org.apache.activemq.transport.amqp.interop.AmqpFlowControlTest-output.txt",
        "Sent message: 1000",
    ),
    (
        "heartbeat_activity",
        "activemq",
        "activemq/activemq-amqp/target/surefire-reports/org.apache.activemq.transport.amqp.interop.AmqpClientRequestsHeartbeatsTest-output.txt",
        "Client performing next idle check",
    ),
    (
        "stomp_ssl_endpoint",
        "activemq",
        "activemq/activemq-stomp/target/surefire-reports/org.apache.activemq.transport.stomp.StompSslTest-output.txt",
        "Using stomp+ssl port",
    ),
    (
        "shared_store_slave_mode",
        "activemq",
        "activemq/activemq-unit-tests/target/surefire-reports/org.apache.activemq.broker.jmx.JMXMasterSlaveSharedStoreTest-output.txt",
        "This broker is now in slave mode",
    ),
]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def infer_module(rel_path: str) -> str:
    parts = Path(rel_path).parts
    return parts[1] if len(parts) > 1 else parts[0]


def choose_line(path: Path, needle: str) -> tuple[int, str]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for idx, line in enumerate(lines, start=1):
        if needle in line:
            return idx, line
    raise RuntimeError(f"Could not find '{needle}' in {path}")


def build_zookeeper_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected = []
    for semantic_group, needle in ZK_SEMANTIC_SPECS:
        match = None
        for row in rows:
            start_line = int(row["SegmentStartLine"])
            for offset, line in enumerate(row["SegmentText"].splitlines()):
                if needle not in line:
                    continue
                match = {
                    "SemanticGroup": semantic_group,
                    "Repo": row["Repo"],
                    "TestName": row["TestName"],
                    "RelativePath": row["RelativePath"],
                    "SourceLine": str(start_line + offset),
                    "LogMessage": line,
                }
                break
            if match:
                break
        if not match:
            raise RuntimeError(f"Could not find zookeeper semantic message for {semantic_group}")
        selected.append(
            match
        )
    return selected


def build_supplement_rows() -> list[dict[str, str]]:
    selected = []
    for semantic_group, repo, rel_path, needle in SUPPLEMENT_SPECS:
        path = DEFAULT_LOG_ROOT / rel_path
        source_line, log_message = choose_line(path, needle)
        selected.append(
            {
                "SemanticGroup": semantic_group,
                "Repo": repo,
                "TestName": Path(rel_path).name.replace("-output.txt", ""),
                "RelativePath": rel_path,
                "SourceLine": str(source_line),
                "LogMessage": log_message,
            }
        )
    return selected


def main() -> None:
    zk_rows = build_zookeeper_rows(load_csv(DEFAULT_ZK_INPUT))
    supplement_rows = build_supplement_rows()
    rows = zk_rows + supplement_rows
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with DEFAULT_OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {DEFAULT_OUTPUT}")


if __name__ == "__main__":
    main()
