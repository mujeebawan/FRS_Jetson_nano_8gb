import { useState } from "react"
import { ZoomIn, ZoomOut, RotateCcw, Loader2 } from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import { Label } from "@/components/ui/label"
import api from "@/services/api"

interface CameraSettingsProps {
  cameraInfo: {
    connected: boolean
    model?: string
    resolution?: string
  } | null
}

export function CameraSettings({ cameraInfo }: CameraSettingsProps) {
  const [zoomLevel, setZoomLevel] = useState(0)
  const [zooming, setZooming] = useState(false)

  const handleZoom = async (action: "in" | "out") => {
    setZooming(true)
    try {
      if (action === "in") {
        await api.system.zoomIn()
        setZoomLevel((prev) => Math.min(prev + 10, 100))
      } else {
        await api.system.zoomOut()
        setZoomLevel((prev) => Math.max(prev - 10, 0))
      }
    } catch {
      console.error("Zoom failed")
    } finally {
      setTimeout(async () => {
        try {
          await api.system.zoomStop()
        } catch {
          // Ignore
        }
        setZooming(false)
      }, 500)
    }
  }

  const handleZoomSet = async (level: number) => {
    setZooming(true)
    try {
      await api.system.zoomSet(level)
      setZoomLevel(level)
    } catch {
      console.error("Failed to set zoom")
    } finally {
      setZooming(false)
    }
  }

  const handleReset = async () => {
    await handleZoomSet(0)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Camera Controls</CardTitle>
        <CardDescription>
          Control camera PTZ (Pan-Tilt-Zoom) settings
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Camera Info */}
        {cameraInfo && (
          <div className="rounded-lg border p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Status</span>
              <span className={`font-medium ${cameraInfo.connected ? "text-green-500" : "text-red-500"}`}>
                {cameraInfo.connected ? "Connected" : "Disconnected"}
              </span>
            </div>
            {cameraInfo.model && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Model</span>
                <span className="font-medium">{cameraInfo.model}</span>
              </div>
            )}
            {cameraInfo.resolution && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Resolution</span>
                <span className="font-medium">{cameraInfo.resolution}</span>
              </div>
            )}
          </div>
        )}

        {/* Zoom Controls */}
        <div className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Optical Zoom</Label>
              <span className="text-sm text-muted-foreground">{zoomLevel}%</span>
            </div>
            <Slider
              value={[zoomLevel]}
              onValueChange={([value]) => handleZoomSet(value)}
              min={0}
              max={100}
              step={5}
              disabled={zooming || !cameraInfo?.connected}
            />
          </div>

          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => handleZoom("out")}
              disabled={zooming || !cameraInfo?.connected || zoomLevel <= 0}
            >
              {zooming ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <ZoomOut className="mr-2 h-4 w-4" />
              )}
              Zoom Out
            </Button>
            <Button
              variant="outline"
              onClick={handleReset}
              disabled={zooming || !cameraInfo?.connected || zoomLevel === 0}
            >
              <RotateCcw className="mr-2 h-4 w-4" />
              Reset
            </Button>
            <Button
              variant="outline"
              onClick={() => handleZoom("in")}
              disabled={zooming || !cameraInfo?.connected || zoomLevel >= 100}
            >
              {zooming ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <ZoomIn className="mr-2 h-4 w-4" />
              )}
              Zoom In
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
