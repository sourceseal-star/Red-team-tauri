// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod state;

fn main() {
    env_logger::init();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_process::init())
        .invoke_handler(tauri::generate_handler![
            commands::get_services_status,
            commands::start_service,
            commands::stop_service,
            commands::restart_service,
            commands::start_all_services,
            commands::stop_all_services,
            commands::get_system_resources,
            commands::get_service_logs,
            commands::get_config_files,
            commands::read_config_file,
            commands::write_config_file,
            commands::get_report_list,
            commands::get_report_detail,
            commands::get_honeypot_status,
            commands::toggle_honeypot,
            commands::rotate_tokens,
            commands::get_soar_dags,
            commands::save_soar_dag,
            commands::dry_run_soar,
            commands::get_tip_iocs,
            commands::import_stix,
            commands::get_rasp_devices,
            commands::revoke_device,
            commands::run_terminal_command,
            commands::get_settings,
            commands::save_settings,
            commands::reset_all,
        ])
        .manage(state::AppState::default())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
