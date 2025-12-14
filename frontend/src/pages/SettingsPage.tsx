import { useState, useEffect } from "react"
import { Loader2 } from "lucide-react"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  DetectionSettings,
  RecognitionSettings,
  StorageSettings,
  CameraSettings,
} from "@/components/settings"
import api from "@/services/api"

interface Settings {
  detection_confidence: number
  recognition_threshold: number
  frame_skip: number
  enable_motion_trigger: boolean
  alert_cooldown_seconds: number
  video_recording_enabled: boolean
  video_clip_duration: number
}

interface CameraInfo {
  connected: boolean
  model?: string
  resolution?: string
}

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [cameraInfo, setCameraInfo] = useState<CameraInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const [settingsData, cameraData] = await Promise.all([
          api.system.getSettings(),
          api.system.cameraInfo().catch(() => null),
        ])
        setSettings(settingsData)
        setCameraInfo(cameraData)
        setError(null)
      } catch {
        setError("Failed to load settings")
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  const handleSaveSettings = async (updates: Partial<Settings>) => {
    try {
      await api.system.updateSettings(updates)
      // Refresh settings
      const newSettings = await api.system.getSettings()
      setSettings(newSettings)
    } catch {
      throw new Error("Failed to save settings")
    }
  }

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  if (error || !settings) {
    return (
      <div className="flex h-96 items-center justify-center">
        <p className="text-destructive">{error || "Failed to load settings"}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">
          Configure system settings and preferences
        </p>
      </div>

      {/* Settings Tabs */}
      <Tabs defaultValue="detection" className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="detection">Detection</TabsTrigger>
          <TabsTrigger value="recognition">Recognition</TabsTrigger>
          <TabsTrigger value="camera">Camera</TabsTrigger>
          <TabsTrigger value="storage">Storage</TabsTrigger>
        </TabsList>

        <TabsContent value="detection">
          <DetectionSettings
            settings={{
              detection_confidence: settings.detection_confidence,
              frame_skip: settings.frame_skip,
              enable_motion_trigger: settings.enable_motion_trigger,
            }}
            onSave={handleSaveSettings}
          />
        </TabsContent>

        <TabsContent value="recognition">
          <RecognitionSettings
            settings={{
              recognition_threshold: settings.recognition_threshold,
              alert_cooldown_seconds: settings.alert_cooldown_seconds,
              video_recording_enabled: settings.video_recording_enabled,
              video_clip_duration: settings.video_clip_duration,
            }}
            onSave={handleSaveSettings}
          />
        </TabsContent>

        <TabsContent value="camera">
          <CameraSettings cameraInfo={cameraInfo} />
        </TabsContent>

        <TabsContent value="storage">
          <StorageSettings />
        </TabsContent>
      </Tabs>
    </div>
  )
}
