import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Progress } from '@/components/ui/progress';
import { AlertTriangle, Camera, Router, Server, Shield, Wifi, XCircle, CheckCircle, Loader2 } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

// Tipos
interface Device {
  ip: string;
  vendor: string;
  type: string;
  model: string;
  os: string;
  risk: string;
  ports: number[];
  services: string[];
  first_seen: string;
  last_seen: string;
  status: string;
  alerts: number;
  is_new: boolean;
}

interface ScanResult {
  ip: string;
  services: Array<{
    port: number;
    service: string;
    banner: string | null;
    vulnerable: boolean;
    creds: string | null;
    device_info: Device;
  }>;
  info: Device;
}

interface Alert {
  id: number;
  device_ip: string;
  alert_type: string;
  severity: string;
  title: string;
  description: string;
  timestamp: string;
  resolved: boolean;
}

interface OrchestratorStatus {
  running: boolean;
  last_scan: string | null;
  last_alert: string | null;
  devices: {
    total: number;
    active: number;
    inactive: number;
    new: number;
    high_risk: number;
  };
  alerts: {
    unresolved: number;
    total: number;
  };
}

// Componente principal
export const SealPanel: React.FC = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [devices, setDevices] = useState<Device[]>([]);
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [status, setStatus] = useState<OrchestratorStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  const { toast } = useToast();

  // Cargar datos
  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      // Simular carga de datos (en producción, esto sería una llamada API)
      // Para el demo, usamos datos de ejemplo
      const mockDevices: Device[] = [
        {
          ip: '192.168.0.1',
          vendor: 'Tenda',
          type: 'Router/AP',
          model: 'AC10',
          os: 'Linux',
          risk: 'medium',
          ports: [80, 443, 8080],
          services: ['HTTP', 'HTTPS', 'HTTP-Proxy'],
          first_seen: '2026-08-21T10:00:00',
          last_seen: '2026-08-21T15:30:00',
          status: 'active',
          alerts: 0,
          is_new: false,
        },
        {
          ip: '192.168.0.7',
          vendor: 'Hikvision',
          type: 'Camera/DVR',
          model: 'DS-2CD2043G2-IU',
          os: 'Embedded Linux',
          risk: 'high',
          ports: [80, 554, 8000],
          services: ['HTTP', 'RTSP', 'ONVIF'],
          first_seen: '2026-08-21T10:05:00',
          last_seen: '2026-08-21T15:30:00',
          status: 'active',
          alerts: 2,
          is_new: false,
        },
        {
          ip: '192.168.0.2',
          vendor: 'Unknown',
          type: 'Unknown',
          model: 'Unknown',
          os: 'Unknown',
          risk: 'low',
          ports: [80],
          services: ['HTTP'],
          first_seen: '2026-08-21T14:00:00',
          last_seen: '2026-08-21T15:30:00',
          status: 'active',
          alerts: 0,
          is_new: true,
        },
      ];

      const mockScanResults: ScanResult[] = [
        {
          ip: '192.168.0.1',
          services: [
            { port: 80, service: 'http', banner: 'Server: Tenda Technology', vulnerable: false, creds: null, device_info: mockDevices[0] },
            { port: 443, service: 'https', banner: 'Server: Tenda Technology', vulnerable: false, creds: null, device_info: mockDevices[0] },
            { port: 8080, service: 'http-proxy', banner: null, vulnerable: false, creds: null, device_info: mockDevices[0] },
          ],
          info: mockDevices[0],
        },
        {
          ip: '192.168.0.7',
          services: [
            { port: 80, service: 'http', banner: 'Server: Hikvision Web Server', vulnerable: true, creds: 'admin:12345', device_info: mockDevices[1] },
            { port: 554, service: 'rtsp', banner: 'RTSP/1.0 200 OK', vulnerable: true, creds: 'admin:12345', device_info: mockDevices[1] },
            { port: 8000, service: 'onvif', banner: 'ONVIF Device', vulnerable: false, creds: null, device_info: mockDevices[1] },
          ],
          info: mockDevices[1],
        },
        {
          ip: '192.168.0.2',
          services: [
            { port: 80, service: 'http', banner: 'Server: nginx/1.8.0', vulnerable: false, creds: null, device_info: mockDevices[2] },
          ],
          info: mockDevices[2],
        },
      ];

      const mockAlerts: Alert[] = [
        {
          id: 1,
          device_ip: '192.168.0.7',
          alert_type: 'vulnerable_device',
          severity: 'high',
          title: 'Dispositivo vulnerable detectado',
          description: 'La cámara Hikvision en 192.168.0.7 tiene credenciales por defecto',
          timestamp: '2026-08-21T15:15:00',
          resolved: false,
        },
        {
          id: 2,
          device_ip: '192.168.0.7',
          alert_type: 'new_device',
          severity: 'info',
          title: 'Nueva cámara detectada',
          description: 'Se ha detectado una nueva cámara Hikvision en la red',
          timestamp: '2026-08-21T10:05:00',
          resolved: true,
        },
      ];

      const mockStatus: OrchestratorStatus = {
        running: true,
        last_scan: '2026-08-21T15:30:00',
        last_alert: '2026-08-21T15:15:00',
        devices: {
          total: 3,
          active: 3,
          inactive: 0,
          new: 1,
          high_risk: 1,
        },
        alerts: {
          unresolved: 1,
          total: 2,
        },
      };

      setDevices(mockDevices);
      setScanResults(mockScanResults);
      setAlerts(mockAlerts);
      setStatus(mockStatus);
    } catch (error) {
      console.error('Error cargando datos:', error);
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'No se pudo cargar los datos',
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    
    // Refrescar cada 30 segundos
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Iniciar/detener escaneo
  const handleScanToggle = async () => {
    if (isScanning) return;
    
    setIsScanning(true);
    try {
      // Simular escaneo
      await new Promise(resolve => setTimeout(resolve, 3000));
      toast({
        title: 'Escaneo completado',
        description: 'Se han detectado 3 dispositivos en la red',
      });
      fetchData();
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'No se pudo completar el escaneo',
      });
    } finally {
      setIsScanning(false);
    }
  };

  // Iniciar/detener orquestador
  const handleOrchestratorToggle = async () => {
    const newStatus = !status?.running;
    
    try {
      // Simular cambio de estado
      setStatus(prev => prev ? { ...prev, running: newStatus } : null);
      
      toast({
        title: newStatus ? 'Orquestador iniciado' : 'Orquestador detenido',
        description: `El orquestador está ahora ${newStatus ? 'en ejecución' : 'detenido'}`,
      });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'No se pudo cambiar el estado del orquestador',
      });
    }
  };

  // Resolver alerta
  const handleResolveAlert = (alertId: number) => {
    setAlerts(prev => 
      prev.map(alert => 
        alert.id === alertId ? { ...alert, resolved: true } : alert
      )
    );
    toast({
      title: 'Alerta resuelta',
      description: `Alerta #${alertId} marcada como resuelta`,
    });
  };

  // Obtener icono por tipo de dispositivo
  const getDeviceIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'camera':
      case 'camera/dvr':
        return <Camera className="h-4 w-4" />;
      case 'router':
      case 'router/ap':
        return <Wifi className="h-4 w-4" />;
      case 'server':
        return <Server className="h-4 w-4" />;
      default:
        return <Server className="h-4 w-4" />;
    }
  };

  // Obtener color por nivel de riesgo
  const getRiskColor = (risk: string) => {
    switch (risk.toLowerCase()) {
      case 'critical':
        return 'bg-red-500';
      case 'high':
        return 'bg-orange-500';
      case 'medium':
        return 'bg-yellow-500';
      default:
        return 'bg-green-500';
    }
  };

  // Obtener variante de badge por nivel de riesgo
  const getRiskVariant = (risk: string) => {
    switch (risk.toLowerCase()) {
      case 'critical':
        return 'destructive';
      case 'high':
        return 'default';
      case 'medium':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin" />
          <p>Cargando datos...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">🔥 SEAL SUPER PACK</h1>
          <p className="text-muted-foreground">Sistema Completo de Inteligencia de Red</p>
        </div>
        <div className="flex gap-2">
          <Button 
            onClick={handleScanToggle} 
            disabled={isScanning}
          >
            {isScanning ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Escaneando...
              </>
            ) : (
              '🔍 Escanear Red'
            )}
          </Button>
          <Button 
            onClick={handleOrchestratorToggle}
            variant={status?.running ? 'destructive' : 'default'}
          >
            {status?.running ? '🛑 Detener Orquestador' : '▶️ Iniciar Orquestador'}
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Dispositivos Totales</CardTitle>
            <Wifi className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{status?.devices.total || 0}</div>
            <p className="text-xs text-muted-foreground">
              {status?.devices.active || 0} activos, {status?.devices.inactive || 0} inactivos
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cámaras</CardTitle>
            <Camera className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {devices.filter(d => d.type.toLowerCase().includes('camera')).length}
            </div>
            <p className="text-xs text-muted-foreground">
              Dispositivos de vigilancia
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Alertas</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{status?.alerts.unresolved || 0}</div>
            <p className="text-xs text-muted-foreground">
              {status?.alerts.total || 0} totales
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Riesgo Alto</CardTitle>
            <Shield className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{status?.devices.high_risk || 0}</div>
            <p className="text-xs text-muted-foreground">
              Dispositivos vulnerables
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="mb-6">
        <TabsList className="grid w-full md:w-auto grid-cols-4 lg:grid-cols-6">
          <TabsTrigger value="dashboard">📊 Dashboard</TabsTrigger>
          <TabsTrigger value="devices">📱 Dispositivos</TabsTrigger>
          <TabsTrigger value="scan">🔍 Escaneo</TabsTrigger>
          <TabsTrigger value="alerts">🔔 Alertas</TabsTrigger>
          <TabsTrigger value="arto">🤖 ARTO</TabsTrigger>
          <TabsTrigger value="settings">⚙️ Configuración</TabsTrigger>
        </TabsList>

        {/* Dashboard Tab */}
        <TabsContent value="dashboard">
          <div className="space-y-4">
            {/* Estado del Orquestador */}
            <Card>
              <CardHeader>
                <CardTitle>Estado del Orquestador</CardTitle>
                <CardDescription>
                  Monitoreo continuo de la red
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4">
                  <div className={`w-3 h-3 rounded-full ${status?.running ? 'bg-green-500' : 'bg-red-500'}`} />
                  <span className="font-medium">
                    {status?.running ? '✅ En ejecución' : '❌ Detenido'}
                  </span>
                </div>
                <div className="mt-4 grid gap-2">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Último escaneo:</span>
                    <span>{status?.last_scan || 'Nunca'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Última alerta:</span>
                    <span>{status?.last_alert || 'Nunca'}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Distribución de dispositivos */}
            <Card>
              <CardHeader>
                <CardTitle>Distribución de Dispositivos</CardTitle>
                <CardDescription>
                  Tipos de dispositivos en la red
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {['Camera/DVR', 'Router/AP', 'Server', 'Unknown'].map(type => {
                    const count = devices.filter(d => d.type === type).length;
                    const percentage = (count / devices.length * 100).toFixed(1);
                    return (
                      <div key={type} className="space-y-1">
                        <div className="flex justify-between text-sm">
                          <span>{type}</span>
                          <span>{count} ({percentage}%)</span>
                        </div>
                        <Progress value={parseFloat(percentage)} className="h-2" />
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            {/* Dispositivos recientes */}
            <Card>
              <CardHeader>
                <CardTitle>Dispositivos Recientes</CardTitle>
                <CardDescription>
                  Últimos dispositivos detectados
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>IP</TableHead>
                      <TableHead>Tipo</TableHead>
                      <TableHead>Vendor</TableHead>
                      <TableHead>Riesgo</TableHead>
                      <TableHead>Estado</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {devices
                      .sort((a, b) => new Date(b.first_seen).getTime() - new Date(a.first_seen).getTime())
                      .slice(0, 5)
                      .map(device => (
                        <TableRow key={device.ip}>
                          <TableCell className="font-medium">{device.ip}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              {getDeviceIcon(device.type)}
                              {device.type}
                            </div>
                          </TableCell>
                          <TableCell>{device.vendor}</TableCell>
                          <TableCell>
                            <Badge variant={getRiskVariant(device.risk)}>
                              {device.risk}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Badge variant={device.status === 'active' ? 'default' : 'secondary'}>
                              {device.status}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Devices Tab */}
        <TabsContent value="devices">
          <Card>
            <CardHeader>
              <CardTitle>Lista de Dispositivos</CardTitle>
              <CardDescription>
                Todos los dispositivos detectados en la red
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>IP</TableHead>
                    <TableHead>Vendor</TableHead>
                    <TableHead>Modelo</TableHead>
                    <TableHead>Tipo</TableHead>
                    <TableHead>OS</TableHead>
                    <TableHead>Riesgo</TableHead>
                    <TableHead>Puertos</TableHead>
                    <TableHead>Alertas</TableHead>
                    <TableHead>Estado</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {devices.map(device => (
                    <TableRow key={device.ip}>
                      <TableCell className="font-medium">{device.ip}</TableCell>
                      <TableCell>{device.vendor}</TableCell>
                      <TableCell>{device.model}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {getDeviceIcon(device.type)}
                          {device.type}
                        </div>
                      </TableCell>
                      <TableCell>{device.os}</TableCell>
                      <TableCell>
                        <Badge variant={getRiskVariant(device.risk)}>
                          {device.risk}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {device.ports.slice(0, 3).join(', ')}
                        {device.ports.length > 3 && '...'}
                      </TableCell>
                      <TableCell>
                        {device.alerts > 0 && (
                          <Badge variant="destructive">{device.alerts}</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant={device.status === 'active' ? 'default' : 'secondary'}>
                          {device.status}
                        </Badge>
                        {device.is_new && (
                          <Badge variant="outline" className="ml-2">Nuevo</Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Scan Tab */}
        <TabsContent value="scan">
          <div className="space-y-4">
            {scanResults.map(result => (
              <Card key={result.ip}>
                <CardHeader>
                  <CardTitle>{result.ip}</CardTitle>
                  <CardDescription>
                    {result.info.vendor} {result.info.model} - {result.info.type}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <h3 className="font-medium">Servicios detectados:</h3>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Puerto</TableHead>
                          <TableHead>Servicio</TableHead>
                          <TableHead>Banner</TableHead>
                          <TableHead>Vulnerable</TableHead>
                          <TableHead>Credenciales</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {result.services.map(service => (
                          <TableRow key={`${result.ip}-${service.port}`}>
                            <TableCell>{service.port}</TableCell>
                            <TableCell>{service.service}</TableCell>
                            <TableCell className="max-w-[300px] truncate">
                              {service.banner || 'No banner'}
                            </TableCell>
                            <TableCell>
                              {service.vulnerable ? (
                                <CheckCircle className="h-4 w-4 text-red-500" />
                              ) : (
                                <XCircle className="h-4 w-4 text-green-500" />
                              )}
                            </TableCell>
                            <TableCell>
                              {service.creds && (
                                <Badge variant="destructive">{service.creds}</Badge>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Alerts Tab */}
        <TabsContent value="alerts">
          <Card>
            <CardHeader>
              <CardTitle>Alertas del Sistema</CardTitle>
              <CardDescription>
                Alertas generadas por el monitoreo continuo
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {alerts
                  .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
                  .map(alert => (
                    <Alert 
                      key={alert.id}
                      variant={alert.severity === 'critical' || alert.severity === 'high' ? 'destructive' : 'default'}
                    >
                      <AlertTriangle className="h-4 w-4" />
                      <div className="flex-1">
                        <AlertTitle className="flex items-center justify-between">
                          {alert.title}
                          {!alert.resolved && (
                            <Button 
                              size="sm" 
                              variant="ghost" 
                              onClick={() => handleResolveAlert(alert.id)}
                            >
                              Marcar como resuelta
                            </Button>
                          )}
                        </AlertTitle>
                        <AlertDescription>
                          <div className="grid gap-2">
                            <div>
                              <span className="font-medium">Dispositivo:</span> {alert.device_ip}
                            </div>
                            <div>
                              <span className="font-medium">Tipo:</span> {alert.alert_type}
                            </div>
                            <div>
                              <span className="font-medium">Gravedad:</span> 
                              <Badge variant={getRiskVariant(alert.severity)}>
                                {alert.severity}
                              </Badge>
                            </div>
                            <div>
                              <span className="font-medium">Fecha:</span> {alert.timestamp}
                            </div>
                            <div>
                              <span className="font-medium">Descripción:</span> {alert.description}
                            </div>
                            <div>
                              <span className="font-medium">Estado:</span> 
                              <Badge variant={alert.resolved ? 'outline' : 'secondary'}>
                                {alert.resolved ? 'Resuelta' : 'No resuelta'}
                              </Badge>
                            </div>
                          </div>
                        </AlertDescription>
                      </div>
                    </Alert>
                  ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ARTO Tab */}
        <TabsContent value="arto">
          <Card>
            <CardHeader>
              <CardTitle>Integración con ARTO</CardTitle>
              <CardDescription>
                Sistema de Operaciones Autónomas de Red Team
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                <div>
                  <h3 className="font-medium mb-2">Análisis Autónomo</h3>
                  <p className="text-muted-foreground text-sm">
                    ARTO analiza automáticamente los dispositivos detectados y recomienda acciones.
                  </p>
                </div>

                <div>
                  <h3 className="font-medium mb-2">Capacidades</h3>
                  <div className="grid gap-2">
                    {[
                      { name: 'Análisis de riesgo', description: 'Evaluación automática de vulnerabilidades' },
                      { name: 'Inteligencia de amenazas', description: 'Búsqueda en bases de datos de amenazas' },
                      { name: 'Predicciones', description: 'Análisis predictivo de ataques' },
                      { name: 'Simulación de ataques', description: 'Pruebas de penetración simuladas' },
                      { name: 'Generación de informes', description: 'Informes detallados de seguridad' },
                    ].map((capability, index) => (
                      <Card key={index} className="p-4">
                        <div className="flex items-center gap-4">
                          <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                            <Shield className="h-4 w-4 text-primary" />
                          </div>
                          <div>
                            <h4 className="font-medium">{capability.name}</h4>
                            <p className="text-sm text-muted-foreground">{capability.description}</p>
                          </div>
                        </div>
                      </Card>
                    ))}
                  </div>
                </div>

                <div>
                  <h3 className="font-medium mb-2">Acciones Recomendadas</h3>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Dispositivo</TableHead>
                        <TableHead>Acción</TableHead>
                        <TableHead>Prioridad</TableHead>
                        <TableHead>Razón</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {devices
                        .filter(d => d.risk === 'high' || d.risk === 'critical')
                        .map(device => (
                          <TableRow key={device.ip}>
                            <TableCell>{device.ip}</TableCell>
                            <TableCell>
                              <Badge variant="default">
                                {device.risk === 'critical' ? 'Ataque inmediato' : 'Escaneo profundo'}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <Badge variant={device.risk === 'critical' ? 'destructive' : 'default'}>
                                {device.risk.toUpperCase()}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              Dispositivo {device.vendor} {device.model} con riesgo {device.risk}
                            </TableCell>
                          </TableRow>
                        ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings">
          <Card>
            <CardHeader>
              <CardTitle>Configuración</CardTitle>
              <CardDescription>
                Configuración del SEAL SUPER PACK
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <h3 className="font-medium mb-2">Configuración de Red</h3>
                <div className="grid gap-4">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Red a escanear</span>
                    <span className="font-medium">192.168.1.0/24</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Intervalo de escaneo</span>
                    <span className="font-medium">15 minutos</span>
                  </div>
                </div>
              </div>

              <div>
                <h3 className="font-medium mb-2">Configuración de ARTO</h3>
                <div className="grid gap-4">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">URL de ARTO</span>
                    <span className="font-medium">http://localhost:8001/arto</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Integración activa</span>
                    <span className="font-medium">✅ Sí</span>
                  </div>
                </div>
              </div>

              <div>
                <h3 className="font-medium mb-2">Acciones</h3>
                <div className="flex gap-2">
                  <Button variant="outline">Guardar configuración</Button>
                  <Button variant="outline">Exportar datos</Button>
                  <Button variant="outline">Limpiar base de datos</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Footer */}
      <div className="mt-8 text-center text-sm text-muted-foreground">
        <p>SEAL SUPER PACK v2.0.0 | SourceSeal Red Team | {new Date().toLocaleDateString()}</p>
      </div>
    </div>
  );
};

export default SealPanel;
