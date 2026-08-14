use std::collections::HashMap;
use std::sync::Arc;
use std::time::Instant;
use tokio::sync::Mutex;

#[derive(Default)]
pub struct AppState {
    pub services: Arc<Mutex<HashMap<String, ServiceProcess>>>,
}

pub struct ServiceProcess {
    pub pid: u32,
    pub started_at: Instant,
    pub handle: tokio::process::Child,
}

impl ServiceProcess {
    pub async fn kill(&mut self) -> anyhow::Result<()> {
        self.handle.kill().await?;
        Ok(())
    }
}
