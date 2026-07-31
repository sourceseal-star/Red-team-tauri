#!/usr/bin/env python3
"""
SOAR Playbook DAG Engine
========================
An advanced Security Orchestration, Automation, and Response engine executing playbooks as
Directed Acyclic Graphs (DAGs). Supports parallel execution, timeouts, audit logs, and dry-run mode.
"""

import time
import json
import datetime
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Set, Union, Callable

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("soar.playbooks")


class NodeState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ExecutionResult:
    status: NodeState
    detail: str
    duration_ms: float
    timestamp: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat() + "Z")
    retries: int = 0


@dataclass
class DAGNode:
    name: str
    action_type: str  # block_ip, isolate_endpoint, revoke_token, send_alert, create_ticket, update_firewall, rate_limit_ip
    target: str       # e.g., "192.168.1.100", "user@domain.com", "device_id"
    conditions: Dict[str, Any] = field(default_factory=dict)  # e.g. {"severity": "critical"}
    on_success: Optional[Union[str, List[str]]] = None        # next node(s) on success
    on_failure: Optional[Union[str, List[str]]] = None        # next node(s) on failure
    state: NodeState = NodeState.PENDING
    timeout: float = 30.0                                     # Timeout per node in seconds
    result: Optional[ExecutionResult] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


class PlaybookDAG:
    """Represents a DAG of execution steps for a response playbook."""
    
    def __init__(self, name: str, description: str = ""):
        self.name: str = name
        self.description: str = description
        self.nodes: Dict[str, DAGNode] = {}
        self.root_nodes: Set[str] = set()
        # Track edge dependencies to find out which nodes are roots and resolve execution paths
        self.incoming_dependencies: Dict[str, Set[str]] = {}

    def add_node(self, node: DAGNode) -> None:
        """Adds a node to the DAG."""
        self.nodes[node.name] = node
        self.incoming_dependencies.setdefault(node.name, set())
        # By default, every added node is a root until proven otherwise (has an incoming edge)
        self.root_nodes.add(node.name)

    def add_edge(self, from_node_name: str, to_node_name: str, on_success_edge: bool = True) -> None:
        """Explicitly defines an execution dependency edge."""
        if from_node_name not in self.nodes or to_node_name not in self.nodes:
            raise ValueError(f"Nodes must exist before adding edges: {from_node_name} -> {to_node_name}")
        
        from_node = self.nodes[from_node_name]
        
        # Populate DAG fields
        if on_success_edge:
            if from_node.on_success is None:
                from_node.on_success = to_node_name
            elif isinstance(from_node.on_success, str):
                from_node.on_success = [from_node.on_success, to_node_name]
            elif isinstance(from_node.on_success, list):
                from_node.on_success.append(to_node_name)
        else:
            if from_node.on_failure is None:
                from_node.on_failure = to_node_name
            elif isinstance(from_node.on_failure, str):
                from_node.on_failure = [from_node.on_failure, to_node_name]
            elif isinstance(from_node.on_failure, list):
                from_node.on_failure.append(to_node_name)
                
        self.incoming_dependencies.setdefault(to_node_name, set()).add(from_node_name)
        if to_node_name in self.root_nodes:
            self.root_nodes.remove(to_node_name)

    def get_successors(self, node_name: str, success: bool = True) -> List[str]:
        """Gets the list of successor nodes based on execution status."""
        node = self.nodes.get(node_name)
        if not node:
            return []
        
        edges = node.on_success if success else node.on_failure
        if not edges:
            return []
        if isinstance(edges, str):
            return [edges]
        return list(edges)

    def reset(self) -> None:
        """Resets the state of all nodes in the DAG for a clean execution run."""
        for node in self.nodes.values():
            node.state = NodeState.PENDING
            node.result = None
            node.started_at = None
            node.finished_at = None


# Predefined Playbooks builder function
def create_predefined_playbook(name: str, target: str = "unknown") -> PlaybookDAG:
    """Factory to build predefined playbooks matching requirements."""
    dag = PlaybookDAG(name=name, description=f"Automatic response for {name}")
    
    if name == 'c2_beaconing_response':
        # block_ip -> isolate_endpoint -> revoke_token -> send_alert
        dag.add_node(DAGNode("block_ip", "block_ip", target))
        dag.add_node(DAGNode("isolate_endpoint", "isolate_endpoint", target))
        dag.add_node(DAGNode("revoke_token", "revoke_token", target))
        dag.add_node(DAGNode("send_alert", "send_alert", target))
        
        dag.add_edge("block_ip", "isolate_endpoint")
        dag.add_edge("isolate_endpoint", "revoke_token")
        dag.add_edge("revoke_token", "send_alert")
        
    elif name == 'data_exfiltration_response':
        # block_ip -> isolate_endpoint -> create_ticket -> send_alert -> update_firewall
        dag.add_node(DAGNode("block_ip", "block_ip", target))
        dag.add_node(DAGNode("isolate_endpoint", "isolate_endpoint", target))
        dag.add_node(DAGNode("create_ticket", "create_ticket", target))
        dag.add_node(DAGNode("send_alert", "send_alert", target))
        dag.add_node(DAGNode("update_firewall", "update_firewall", target))
        
        dag.add_edge("block_ip", "isolate_endpoint")
        dag.add_edge("isolate_endpoint", "create_ticket")
        dag.add_edge("create_ticket", "send_alert")
        dag.add_edge("send_alert", "update_firewall")
        
    elif name == 'credential_stuffing_response':
        # block_ip -> revoke_token -> send_alert
        dag.add_node(DAGNode("block_ip", "block_ip", target))
        dag.add_node(DAGNode("revoke_token", "revoke_token", target))
        dag.add_node(DAGNode("send_alert", "send_alert", target))
        
        dag.add_edge("block_ip", "revoke_token")
        dag.add_edge("revoke_token", "send_alert")
        
    elif name == 'api_abuse_response':
        # rate_limit_ip -> block_ip -> send_alert -> create_ticket
        dag.add_node(DAGNode("rate_limit_ip", "rate_limit_ip", target))
        dag.add_node(DAGNode("block_ip", "block_ip", target))
        dag.add_node(DAGNode("send_alert", "send_alert", target))
        dag.add_node(DAGNode("create_ticket", "create_ticket", target))
        
        dag.add_edge("rate_limit_ip", "block_ip")
        dag.add_edge("block_ip", "send_alert")
        dag.add_edge("send_alert", "create_ticket")
        
    elif name == 'malware_detection_response':
        # isolate_endpoint -> revoke_token -> send_alert -> create_ticket
        dag.add_node(DAGNode("isolate_endpoint", "isolate_endpoint", target))
        dag.add_node(DAGNode("revoke_token", "revoke_token", target))
        dag.add_node(DAGNode("send_alert", "send_alert", target))
        dag.add_node(DAGNode("create_ticket", "create_ticket", target))
        
        dag.add_edge("isolate_endpoint", "revoke_token")
        dag.add_edge("revoke_token", "send_alert")
        dag.add_edge("send_alert", "create_ticket")
        
    elif name == 'insider_threat_response':
        # revoke_token -> create_ticket -> send_alert -> update_firewall
        dag.add_node(DAGNode("revoke_token", "revoke_token", target))
        dag.add_node(DAGNode("create_ticket", "create_ticket", target))
        dag.add_node(DAGNode("send_alert", "send_alert", target))
        dag.add_node(DAGNode("update_firewall", "update_firewall", target))
        
        dag.add_edge("revoke_token", "create_ticket")
        dag.add_edge("create_ticket", "send_alert")
        dag.add_edge("send_alert", "update_firewall")
    else:
        raise ValueError(f"Unknown predefined playbook: {name}")
        
    return dag


class PlaybookExecutor:
    """Executes a PlaybookDAG using real or dry-run handlers with timeout and retry capabilities."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run: bool = dry_run
        self.lock = threading.Lock()
        
        # In-memory storage representing simulated production network changes
        self.blocklist: Set[str] = set()
        self.isolated_endpoints: Set[str] = set()
        self.revoked_tokens: Set[str] = set()
        self.sent_alerts: List[Dict[str, Any]] = []
        self.created_tickets: List[Dict[str, Any]] = []
        self.firewall_rules: List[str] = []
        self.rate_limited_ips: Dict[str, str] = {}
        
        # Complete audit trail
        self.audit_trail: List[Dict[str, Any]] = []

    def log_audit(self, node_name: str, action_type: str, target: str, result: ExecutionResult) -> None:
        """Thread-safe logging of audit trails."""
        entry = {
            "node_name": node_name,
            "action_type": action_type,
            "target": target,
            "status": result.status.value,
            "detail": result.detail,
            "duration_ms": result.duration_ms,
            "timestamp": result.timestamp,
            "retries": result.retries
        }
        with self.lock:
            self.audit_trail.append(entry)
            logger.info(f"Audit Log - Node: {node_name} | Action: {action_type} | Target: {target} | Status: {result.status.value} | Retries: {result.retries} | Detail: {result.detail}")

    # --- Handlers ---
    
    def handle_block_ip(self, target: str) -> str:
        if self.dry_run:
            return f"[Dry-Run] Would add {target} to WAF/Firewall blocklist."
        with self.lock:
            self.blocklist.add(target)
        return f"Successfully added IP {target} to edge blocklist."

    def handle_isolate_endpoint(self, target: str) -> str:
        if self.dry_run:
            return f"[Dry-Run] Would isolate endpoint device/IP {target} via ZTNA gateway."
        with self.lock:
            self.isolated_endpoints.add(target)
        return f"Endpoint device/IP {target} has been fully quarantined/isolated."

    def handle_revoke_token(self, target: str) -> str:
        if self.dry_run:
            return f"[Dry-Run] Would revoke active sessions/JWTs for target {target}."
        with self.lock:
            self.revoked_tokens.add(target)
        return f"Revoked all valid JWT tokens and active sessions for user/subject {target}."

    def handle_send_alert(self, target: str) -> str:
        alert_msg = f"CRITICAL incident involving target: {target}"
        if self.dry_run:
            return f"[Dry-Run] Would dispatch Slack/Email notification: '{alert_msg}'"
        with self.lock:
            self.sent_alerts.append({"target": target, "message": alert_msg, "timestamp": time.time()})
        return f"Sent high-priority alert notification to SOC Slack & Email channels."

    def handle_create_ticket(self, target: str) -> str:
        ticket_id = f"INC-2026-{len(self.created_tickets) + 101}"
        if self.dry_run:
            return f"[Dry-Run] Would create Incident Response Ticket for target {target}."
        with self.lock:
            self.created_tickets.append({"ticket_id": ticket_id, "target": target, "status": "Open", "created_at": time.time()})
        return f"Created Incident Ticket {ticket_id} in Case Management System."

    def handle_update_firewall(self, target: str) -> str:
        rule = f"DROP tcp from {target} to any port any"
        if self.dry_run:
            return f"[Dry-Run] Would append rule '{rule}' to firewall."
        with self.lock:
            self.firewall_rules.append(rule)
        return f"Appended rule '{rule}' to perimeter firewall routing policies."

    def handle_rate_limit_ip(self, target: str) -> str:
        limit = "10req/min"
        if self.dry_run:
            return f"[Dry-Run] Would apply aggressive rate limiting of {limit} to IP {target}."
        with self.lock:
            self.rate_limited_ips[target] = limit
        return f"Applied aggressive rate-limiting tier ({limit}) to endpoint {target}."

    def _execute_node_with_retry_and_timeout(self, node: DAGNode, incident_context: Dict[str, Any]) -> ExecutionResult:
        """Executes a single DAG node's action with standard timeouts and up to 3 retries on transient failures."""
        start_time = time.perf_counter()
        
        # Check conditions
        if node.conditions:
            match = True
            for k, v in node.conditions.items():
                if incident_context.get(k) != v:
                    match = False
                    break
            if not match:
                duration_ms = (time.perf_counter() - start_time) * 1000
                return ExecutionResult(
                    status=NodeState.SKIPPED,
                    detail=f"Conditions not met: node conditions {node.conditions} != context {incident_context}",
                    duration_ms=duration_ms
                )

        # Resolve action type handler
        handler_map = {
            "block_ip": self.handle_block_ip,
            "isolate_endpoint": self.handle_isolate_endpoint,
            "revoke_token": self.handle_revoke_token,
            "send_alert": self.handle_send_alert,
            "create_ticket": self.handle_create_ticket,
            "update_firewall": self.handle_update_firewall,
            "rate_limit_ip": self.handle_rate_limit_ip
        }
        
        handler = handler_map.get(node.action_type)
        if not handler:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ExecutionResult(
                status=NodeState.FAILED,
                detail=f"Unsupported action type: {node.action_type}",
                duration_ms=duration_ms
            )

        # Execute with retries & timeout simulation
        max_retries = 3
        attempt = 0
        detail = ""
        status = NodeState.FAILED

        while attempt < max_retries:
            attempt += 1
            node_thread_success = False
            error_msg = ""
            
            def run_wrapper():
                nonlocal node_thread_success, detail, error_msg
                try:
                    # Resolve Target if it has dynamic variables from context
                    resolved_target = node.target
                    if "{" in resolved_target and "}" in resolved_target:
                        resolved_target = resolved_target.format(**incident_context)
                    
                    # Simulate intermittent/transient network failures for testing retry mechanism
                    # e.g., if the target includes "fail_transient", we fail the first two attempts
                    if "fail_transient" in resolved_target and attempt < 3:
                        raise ConnectionResetError("Transient network failure on secure channel connection.")
                    
                    detail = handler(resolved_target)
                    node_thread_success = True
                except Exception as e:
                    error_msg = str(e)

            # Spin up threading wrapper to enforce execution timeout
            t = threading.Thread(target=run_wrapper)
            t.start()
            t.join(timeout=node.timeout)

            if t.is_alive():
                error_msg = f"Execution timed out after {node.timeout} seconds."
                # We can't easily kill Python threads, but we proceed with logging a timeout
            
            if node_thread_success:
                status = NodeState.COMPLETED
                break
            else:
                detail = f"Attempt {attempt} failed: {error_msg}"
                if attempt < max_retries:
                    time.sleep(0.1)  # Brief backoff before retry

        duration_ms = (time.perf_counter() - start_time) * 1000
        return ExecutionResult(
            status=status,
            detail=detail,
            duration_ms=duration_ms,
            retries=attempt - 1
        )

    def execute(self, dag: PlaybookDAG, incident_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a PlaybookDAG using a concurrent workflow runner.
        Independent nodes are executed in parallel via ThreadPoolExecutor.
        """
        logger.info(f"Starting execution of SOAR Playbook DAG: {dag.name}")
        dag.reset()
        
        # Set up scheduling structures
        completed_nodes: Set[str] = set()
        running_nodes: Set[str] = set()
        skipped_nodes: Set[str] = set()
        failed_nodes: Set[str] = set()
        
        # ThreadPoolExecutor for executing independent nodes in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            while len(completed_nodes) + len(skipped_nodes) + len(failed_nodes) < len(dag.nodes):
                # Identify ready nodes: nodes which are PENDING and whose incoming dependencies are resolved
                ready_nodes = []
                for name, node in dag.nodes.items():
                    if node.state != NodeState.PENDING or name in running_nodes:
                        continue
                    
                    # Check if all incoming dependencies have completed execution (or been skipped/failed)
                    deps = dag.incoming_dependencies.get(name, set())
                    deps_resolved = True
                    for dep in deps:
                        dep_node = dag.nodes[dep]
                        if dep_node.state == NodeState.PENDING or dep_node.state == NodeState.RUNNING:
                            deps_resolved = False
                            break
                    
                    if deps_resolved:
                        ready_nodes.append(node)

                if not ready_nodes and not running_nodes:
                    # We are in a deadlock or all remaining nodes are unreachable (due to previous failures/skips)
                    # Let's clean up remaining nodes as skipped
                    for name, node in dag.nodes.items():
                        if node.state == NodeState.PENDING:
                            node.state = NodeState.SKIPPED
                            node.result = ExecutionResult(
                                status=NodeState.SKIPPED,
                                detail="Skipped due to unreachable path or failure in ancestor node.",
                                duration_ms=0.0
                            )
                            skipped_nodes.add(name)
                            self.log_audit(node.name, node.action_type, node.target, node.result)
                    break

                # Submit ready nodes to ThreadPoolExecutor
                futures = {}
                for node in ready_nodes:
                    node.state = NodeState.RUNNING
                    node.started_at = time.time()
                    running_nodes.add(node.name)
                    
                    # Submit task
                    future = executor.submit(self._execute_node_with_retry_and_timeout, node, incident_context)
                    futures[future] = node

                if futures:
                    # Wait for at least one completed execution
                    for future in as_completed(futures):
                        node = futures[future]
                        node.finished_at = time.time()
                        running_nodes.remove(node.name)
                        
                        try:
                            res = future.result()
                        except Exception as e:
                            res = ExecutionResult(
                                status=NodeState.FAILED,
                                detail=f"Unexpected engine crash: {str(e)}",
                                duration_ms=0.0
                            )

                        node.result = res
                        node.state = res.status
                        
                        # Add to the global audit trail
                        self.log_audit(node.name, node.action_type, node.target, res)

                        # Propagate states to children or skip them
                        success = (res.status == NodeState.COMPLETED)
                        
                        # Check successors
                        all_successors = dag.get_successors(node.name, success=True) + dag.get_successors(node.name, success=False)
                        chosen_successors = dag.get_successors(node.name, success=success)
                        
                        # Mark non-chosen paths as skipped if they don't have other valid paths
                        for succ in all_successors:
                            if succ not in chosen_successors:
                                # This child node might be skipped if it depends solely on this failed path
                                pass

                        if res.status == NodeState.COMPLETED:
                            completed_nodes.add(node.name)
                        elif res.status == NodeState.SKIPPED:
                            skipped_nodes.add(node.name)
                        else:
                            failed_nodes.add(node.name)
                            
                        # Break to re-evaluate ready nodes
                        break
                else:
                    # Give thread pool time if running jobs are active
                    time.sleep(0.05)

        logger.info(f"Finished SOAR Playbook execution for: {dag.name}")
        return {
            "playbook_name": dag.name,
            "status": "completed" if not failed_nodes else "failed_with_errors",
            "completed_nodes": list(completed_nodes),
            "failed_nodes": list(failed_nodes),
            "skipped_nodes": list(skipped_nodes)
        }


# Quick test capability to ensure it behaves correctly
if __name__ == "__main__":
    print("Testing Playbook DAG Engine...")
    executor = PlaybookExecutor(dry_run=False)
    
    # Test c2_beaconing_response with a transient fail target to verify retries!
    dag = create_predefined_playbook("c2_beaconing_response", target="fail_transient_192.168.10.5")
    context = {"severity": "critical", "user": "admin"}
    
    summary = executor.execute(dag, context)
    print("\nExecution Summary:")
    print(json.dumps(summary, indent=2))
    
    print("\nAudit Trail:")
    for entry in executor.audit_trail:
        print(f"[{entry['timestamp']}] {entry['node_name']} ({entry['action_type']}) -> Status: {entry['status']}, Retries: {entry['retries']}, Detail: {entry['detail']}")
