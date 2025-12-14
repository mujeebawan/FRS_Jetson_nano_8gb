import { useState, useRef, useEffect, useCallback } from "react"
import {
  Play,
  Pause,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Maximize,
  Minimize,
  RefreshCw,
} from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import api from "@/services/api"

interface LiveStreamCardProps {
  compact?: boolean
}

export function LiveStreamCard({ compact = false }: LiveStreamCardProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [fps, setFps] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [zoomLevel, setZoomLevel] = useState(100)
  const [isZooming, setIsZooming] = useState(false)

  const imgRef = useRef<HTMLImageElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Fetch stream status
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const status = await api.stream.status()
        setIsPlaying(status.is_running)
        setFps(status.fps || 0)
        setError(null)
      } catch {
        setError("Failed to get stream status")
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 2000)
    return () => clearInterval(interval)
  }, [])

  // Handle fullscreen
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement)
    }

    document.addEventListener("fullscreenchange", handleFullscreenChange)
    return () =>
      document.removeEventListener("fullscreenchange", handleFullscreenChange)
  }, [])

  const toggleFullscreen = useCallback(() => {
    if (!containerRef.current) return

    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen()
    } else {
      document.exitFullscreen()
    }
  }, [])

  const handlePlayPause = async () => {
    try {
      if (isPlaying) {
        await api.stream.stop()
      } else {
        await api.stream.start()
      }
      setIsPlaying(!isPlaying)
      setError(null)
    } catch {
      setError("Failed to control stream")
    }
  }

  const handleZoomIn = async () => {
    if (isZooming) return
    setIsZooming(true)
    try {
      await api.system.zoomIn()
      setZoomLevel((prev) => Math.min(prev + 10, 200))
    } catch {
      // Ignore zoom errors
    } finally {
      setTimeout(() => {
        api.system.zoomStop()
        setIsZooming(false)
      }, 500)
    }
  }

  const handleZoomOut = async () => {
    if (isZooming) return
    setIsZooming(true)
    try {
      await api.system.zoomOut()
      setZoomLevel((prev) => Math.max(prev - 10, 100))
    } catch {
      // Ignore zoom errors
    } finally {
      setTimeout(() => {
        api.system.zoomStop()
        setIsZooming(false)
      }, 500)
    }
  }

  const handleZoomReset = async () => {
    try {
      await api.system.zoomSet(0)
      setZoomLevel(100)
    } catch {
      // Ignore zoom errors
    }
  }

  const handleRefresh = () => {
    if (imgRef.current) {
      imgRef.current.src = `${api.stream.getMjpegUrl()}?t=${Date.now()}`
    }
  }

  return (
    <Card ref={containerRef} className={compact ? "" : "col-span-2"}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Live Stream</CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant={isPlaying ? "success" : "secondary"}>
              {isPlaying ? `${fps.toFixed(2)} FPS` : "Stopped"}
            </Badge>
            {zoomLevel > 100 && (
              <Badge variant="outline">{zoomLevel}%</Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="relative aspect-video overflow-hidden rounded-lg bg-black">
          {error ? (
            <div className="flex h-full items-center justify-center text-destructive">
              <p>{error}</p>
            </div>
          ) : isPlaying ? (
            <img
              ref={imgRef}
              src={api.stream.getMjpegUrl()}
              alt="Live Stream"
              className="h-full w-full object-contain"
              onError={() => setError("Stream connection failed")}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              <p>Stream is not running</p>
            </div>
          )}
        </div>

        {/* Controls */}
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              onClick={handlePlayPause}
              title={isPlaying ? "Stop" : "Start"}
            >
              {isPlaying ? (
                <Pause className="h-4 w-4" />
              ) : (
                <Play className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={handleRefresh}
              title="Refresh"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>

          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              onClick={handleZoomOut}
              disabled={isZooming || zoomLevel <= 100}
              title="Zoom Out"
            >
              <ZoomOut className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={handleZoomReset}
              disabled={zoomLevel === 100}
              title="Reset Zoom"
            >
              <RotateCcw className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={handleZoomIn}
              disabled={isZooming || zoomLevel >= 200}
              title="Zoom In"
            >
              <ZoomIn className="h-4 w-4" />
            </Button>
          </div>

          <Button
            variant="outline"
            size="icon"
            onClick={toggleFullscreen}
            title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
          >
            {isFullscreen ? (
              <Minimize className="h-4 w-4" />
            ) : (
              <Maximize className="h-4 w-4" />
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
