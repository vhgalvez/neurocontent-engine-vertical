<#
.SYNOPSIS
    Script avanzado para obtener hardware y datos de sistema.
#>

# Forzamos la ruta del archivo de salida en la misma carpeta del script
$ArchivoSalida = Join-Path $PSScriptRoot "Informe_Hardware_Completo.txt"
$ReporteTexto = New-Object System.Collections.Generic.List[string]

# Función para imprimir en pantalla y guardar en variable para el TXT
function Out-Both {
    param([string]$Texto, [string]$Color = "White")
    Write-Host $Texto -ForegroundColor $Color
    $ReporteTexto.Add($Texto)
}

Clear-Host
$Sep = "==========================================================================================="
Out-Both $Sep "Cyan"
Out-Both "      INFORME DETALLADO DE SISTEMA Y HARDWARE: $env:COMPUTERNAME" "Cyan"
Out-Both "      Fecha: $(Get-Date -Format 'dd/MM/yyyy HH:mm:ss')" "Cyan"
Out-Both $Sep "Cyan"

# --- 1. DATOS DE SYSTEMINFO ---
Out-Both "`n[1] INFORMACION DEL SISTEMA OPERATIVO" "Yellow"
$sysinfoRaw = systeminfo /fo csv | ConvertFrom-Csv
$sysinfoObj = [PSCustomObject]@{
    OS             = $sysinfoRaw."OS Name"
    Version        = $sysinfoRaw."OS Version"
    Instalacion    = $sysinfoRaw."Original Install Date"
    UltimoArranque = $sysinfoRaw."System Boot Time"
}
$sysinfoObj | Format-Table -AutoSize | Out-String | ForEach-Object { Out-Both $_.TrimEnd() }

# --- 2. PLACA BASE Y BIOS ---
Out-Both "[2] PLACA BASE Y BIOS" "Yellow"
$bb = Get-CimInstance Win32_BaseBoard
$bios = Get-CimInstance Win32_BIOS
[PSCustomObject]@{
    Fabricante  = $bb.Manufacturer
    Producto    = $bb.Product
    VersionBIOS = $bios.SMBIOSBIOSVersion
    FechaBIOS   = $bios.ReleaseDate.ToString("dd/MM/yyyy")
} | Format-Table -AutoSize | Out-String | ForEach-Object { Out-Both $_.TrimEnd() }

# --- 3. PROCESADOR (CPU) ---
Out-Both "[3] PROCESADOR" "Yellow"
Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, 
    @{Name="MaxSpeed(MHz)"; Expression={$_.MaxClockSpeed}} | 
    Format-Table -AutoSize | Out-String | ForEach-Object { Out-Both $_.TrimEnd() }

# --- 4. MEMORIA RAM ---
$sysMem = Get-CimInstance Win32_ComputerSystem
Out-Both "[4] MEMORIA RAM (Total: $([Math]::Round($sysMem.TotalPhysicalMemory / 1GB, 2)) GB)" "Yellow"
Get-CimInstance Win32_PhysicalMemory | Select-Object BankLabel, 
    @{Name="Capacidad(GB)"; Expression={$_.Capacity / 1GB}}, 
    @{Name="Velocidad(MT/s)"; Expression={$_.Speed}}, PartNumber | 
    Format-Table -AutoSize | Out-String | ForEach-Object { Out-Both $_.TrimEnd() }

# --- 5. TARJETA GRAFICA (GPU) ---
Out-Both "[5] TARJETA GRAFICA" "Yellow"
Get-CimInstance Win32_VideoController | Select-Object Name, 
    @{Name="Driver_Version"; Expression={$_.DriverVersion}}, 
    @{Name="Resolucion"; Expression={"$($_.CurrentHorizontalResolution)x$($_.CurrentVerticalResolution)"}} | 
    Format-Table -AutoSize | Out-String | ForEach-Object { Out-Both $_.TrimEnd() }

# --- 6. ALMACENAMIENTO ---
Out-Both "[6] UNIDADES DE DISCO" "Yellow"
Get-CimInstance Win32_DiskDrive | Select-Object Model, 
    @{Name="Tamano(GB)"; Expression={[Math]::Round($_.Size / 1GB, 2)}}, 
    MediaType, InterfaceType | 
    Format-Table -AutoSize | Out-String | ForEach-Object { Out-Both $_.TrimEnd() }

# --- 7. RED ---
Out-Both "[7] RED (CONEXIONES ACTIVAS)" "Yellow"
Get-NetAdapter | Where-Object Status -eq "Up" | Select-Object Name, InterfaceDescription, LinkSpeed | 
    Format-Table -AutoSize | Out-String | ForEach-Object { Out-Both $_.TrimEnd() }

Out-Both "`n$Sep" "Cyan"
Out-Both "      INFORME FINALIZADO - Archivo: $ArchivoSalida" "Cyan"
Out-Both $Sep "Cyan"

# Guardar en TXT
$ReporteTexto | Out-File -FilePath $ArchivoSalida -Encoding utf8