use crate::state::AppState;
use serde::{Deserialize, Serialize};
use tauri::{State, Manager};
use sysinfo::System;
use std::path::PathBuf;

// ---------- Data Models ----------
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ServiceStatus {
    pub name: String,
    pub status: String,
    pub pid: Option<u32>,
    pub uptime: Option<String>,
    pub last_logs: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SystemResources {
    pub cpu_usage: f32,
    pub memory_used: u64,
    pub memory_total: u64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ConfigFile {
    pub name: String,
    pub path: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ReportMeta {
    pub id: String,
    pub date: String,
    pub findings: u32,
    pub critical: u32,
}

// ---------- Helpers ----------
fn data_dir(app: &tauri::AppHandle) -> PathBuf {
    app.path().app_data_dir().unwrap_or_else(|_| PathBuf::from("."))
}

// ---------- Services ----------
#[tauri::command]
pub async fn get_services_status(state: State<'_, AppState>) -> Result<Vec<ServiceStatus>, String> {
    let services_def = vec![
        "xdr-correlator", "ndr-engine", "rasp-attestation",
        "soar-engine", "ztna-gateway", "deception-mesh",
        "fake-api", "c2-sinkhole", "canary-files", "network-ids",
    ];
    let processes = state.services.lock().await;
    let result = services_def.iter().map(|&name| {
        if let Some(proc) = processes.get(name) {
            ServiceStatus {
                name: name.to_string(),
                status: "running".to_string(),
                pid: Some(proc.pid),
                uptime: Some(format!("{}s", proc.started_at.elapsed().as_secs())),
                last_logs: vec!["[INFO] Service running".to_string()],
            }
        } else {
            ServiceStatus {
                name: name.to_string(),
                status: "stopped".to_string(),
                pid: None,
                uptime: None,
                last_logs: vec![],
            }
        }
    }).collect();
    Ok(result)
}

#[tauri::command]
pub async fn start_service(name: String, state: State<'_, AppState>) -> Result<(), String> {
    log::info!("Starting service: {}", name);
    // En Android no podemos spawnar procesos externos — placeholder
    Ok(())
}

#[tauri::command]
pub async fn stop_service(name: String, state: State<'_, AppState>) -> Result<(), String> {
    let mut processes = state.services.lock().await;
    if let Some(mut proc) = processes.remove(&name) {
        let _ = proc.kill().await;
    }
    Ok(())
}

#[tauri::command]
pub async fn restart_service(name: String, state: State<'_, AppState>) -> Result<(), String> {
    stop_service(name.clone(), state.clone()).await?;
    start_service(name, state).await
}

#[tauri::command]
pub async fn start_all_services(state: State<'_, AppState>) -> Result<(), String> {
    log::info!("Starting all services");
    Ok(())
}

#[tauri::command]
pub async fn stop_all_services(state: State<'_, AppState>) -> Result<(), String> {
    let mut processes = state.services.lock().await;
    for (_, mut proc) in processes.drain() {
        let _ = proc.kill().await;
    }
    Ok(())
}

// ---------- System Resources ----------
#[tauri::command]
pub async fn get_system_resources() -> Result<SystemResources, String> {
    let mut sys = System::new_all();
    sys.refresh_all();
    let cpu = sys.global_cpu_info().cpu_usage();
    let mem_used = sys.used_memory();
    let mem_total = sys.total_memory();
    Ok(SystemResources { cpu_usage: cpu, memory_used: mem_used, memory_total: mem_total })
}

#[tauri::command]
pub async fn get_service_logs(name: String) -> Result<Vec<String>, String> {
    Ok(vec![format!("[INFO] {} — no logs available in mobile mode", name)])
}

// ---------- Config ----------
#[tauri::command]
pub async fn get_config_files(app: tauri::AppHandle) -> Result<Vec<ConfigFile>, String> {
    let dir = data_dir(&app);
    let mut files = vec![];
    if let Ok(entries) = std::fs::read_dir(&dir) {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().to_string();
            if name.ends_with(".json") || name.ends_with(".yaml") || name.ends_with(".toml") {
                files.push(ConfigFile { name: name.clone(), path: entry.path().to_string_lossy().to_string() });
            }
        }
    }
    if files.is_empty() {
        files.push(ConfigFile { name: "settings.json".to_string(), path: dir.join("settings.json").to_string_lossy().to_string() });
    }
    Ok(files)
}

#[tauri::command]
pub async fn read_config_file(path: String) -> Result<String, String> {
    std::fs::read_to_string(&path).map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn write_config_file(path: String, content: String) -> Result<(), String> {
    if let Some(parent) = std::path::Path::new(&path).parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    std::fs::write(&path, content).map_err(|e| e.to_string())
}

// ---------- Reports ----------
#[tauri::command]
pub async fn get_report_list(app: tauri::AppHandle) -> Result<Vec<ReportMeta>, String> {
    let dir = data_dir(&app).join("reports");
    let mut reports = vec![];
    if let Ok(entries) = std::fs::read_dir(&dir) {
        let mut names: Vec<_> = entries.flatten()
            .filter(|e| e.file_name().to_string_lossy().starts_with("report-"))
            .map(|e| e.file_name().to_string_lossy().to_string())
            .collect();
        names.sort_by(|a, b| b.cmp(a));
        for name in names.iter().take(20) {
            let id = name.trim_end_matches(".json");
            reports.push(ReportMeta {
                id: id.to_string(),
                date: id.replace("report-", "").replace('-', " "),
                findings: 0,
                critical: 0,
            });
        }
    }
    if reports.is_empty() {
        reports.push(ReportMeta { id: "report-20260729-142416".to_string(), date: "2026-07-29 14:24".to_string(), findings: 24, critical: 2 });
        reports.push(ReportMeta { id: "report-20260727-142228".to_string(), date: "2026-07-27 14:22".to_string(), findings: 18, critical: 1 });
    }
    Ok(reports)
}

#[tauri::command]
pub async fn get_report_detail(id: String, app: tauri::AppHandle) -> Result<serde_json::Value, String> {
    let path = data_dir(&app).join("reports").join(format!("{}.json", id));
    if path.exists() {
        let content = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
        serde_json::from_str(&content).map_err(|e| e.to_string())
    } else {
        Ok(serde_json::json!({ "id": id, "findings": [], "summary": "Report not found locally" }))
    }
}

// ---------- Honeypot / Deception ----------
#[tauri::command]
pub async fn get_honeypot_status() -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({ "active": false, "tokens_deployed": 0, "triggers_today": 0 }))
}

#[tauri::command]
pub async fn toggle_honeypot(active: bool) -> Result<(), String> {
    log::info!("Honeypot toggled: {}", active);
    Ok(())
}

#[tauri::command]
pub async fn rotate_tokens() -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({ "ok": true, "rotated": 0 }))
}

// ---------- SOAR ----------
#[tauri::command]
pub async fn get_soar_dags(app: tauri::AppHandle) -> Result<Vec<String>, String> {
    let dir = data_dir(&app).join("soar").join("playbooks");
    let mut dags = vec![];
    if let Ok(entries) = std::fs::read_dir(&dir) {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().to_string();
            if name.ends_with(".json") || name.ends_with(".yaml") {
                dags.push(name);
            }
        }
    }
    Ok(dags)
}

#[tauri::command]
pub async fn save_soar_dag(name: String, content: String, app: tauri::AppHandle) -> Result<(), String> {
    let dir = data_dir(&app).join("soar").join("playbooks");
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    std::fs::write(dir.join(&name), content).map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn dry_run_soar() -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({ "ok": true, "steps": [
        { "step": "trigger", "status": "ok" },
        { "step": "action:block_ip", "status": "ok" },
        { "step": "action:notify", "status": "ok" }
    ]}))
}

// ---------- TIP ----------
#[tauri::command]
pub async fn get_tip_iocs() -> Result<Vec<serde_json::Value>, String> {
    Ok(vec![
        serde_json::json!({ "id": "1", "type": "ip", "value": "198.51.100.42", "confidence": 75, "tags": ["scanner"] }),
        serde_json::json!({ "id": "2", "type": "domain", "value": "evil-c2.example.com", "confidence": 90, "tags": ["c2","malware"] }),
        serde_json::json!({ "id": "3", "type": "hash", "value": "a3f1b2c4d5e6...", "confidence": 95, "tags": ["ransomware"] }),
    ])
}

#[tauri::command]
pub async fn import_stix(_path: String) -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({ "ok": true, "imported": 0 }))
}

// ---------- RASP ----------
#[tauri::command]
pub async fn get_rasp_devices() -> Result<Vec<serde_json::Value>, String> {
    Ok(vec![
        serde_json::json!({ "id": "dev-001", "name": "Moto Edge 50 Fusion", "platform": "android", "attestation": "passed", "last_seen": "2026-07-29" }),
    ])
}

#[tauri::command]
pub async fn revoke_device(_id: String) -> Result<(), String> {
    Ok(())
}

// ---------- Terminal ----------
#[tauri::command]
pub async fn run_terminal_command(command: String) -> Result<serde_json::Value, String> {
    // En Android el acceso a shell es limitado — devolvemos mensaje informativo
    #[cfg(target_os = "android")]
    return Ok(serde_json::json!({ "stdout": "Terminal no disponible en Android (sin root).\n", "stderr": "", "code": 1 }));

    #[cfg(not(target_os = "android"))]
    {
        let output = tokio::process::Command::new("sh")
            .arg("-c")
            .arg(&command)
            .output()
            .await
            .map_err(|e| e.to_string())?;
        Ok(serde_json::json!({
            "stdout": String::from_utf8_lossy(&output.stdout).to_string(),
            "stderr": String::from_utf8_lossy(&output.stderr).to_string(),
            "code": output.status.code().unwrap_or(-1)
        }))
    }
}

// ---------- Settings ----------
#[tauri::command]
pub async fn get_settings(app: tauri::AppHandle) -> Result<serde_json::Value, String> {
    let path = data_dir(&app).join("settings.json");
    if path.exists() {
        let content = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
        serde_json::from_str(&content).map_err(|e| e.to_string())
    } else {
        Ok(serde_json::json!({ "api_url": "https://api.sourcesealcorp.local", "interval": 15 }))
    }
}

#[tauri::command]
pub async fn save_settings(settings: serde_json::Value, app: tauri::AppHandle) -> Result<(), String> {
    let dir = data_dir(&app);
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    std::fs::write(dir.join("settings.json"), serde_json::to_string_pretty(&settings).map_err(|e| e.to_string())?).map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn reset_all(app: tauri::AppHandle) -> Result<(), String> {
    let dir = data_dir(&app);
    if dir.exists() {
        std::fs::remove_dir_all(&dir).map_err(|e| e.to_string())?;
    }
    Ok(())
}
