import { useState } from "react"
import { Loader2 } from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

interface RecognitionSettingsProps {
  settings: {
    recognition_threshold: number
    alert_cooldown_seconds: number
    video_recording_enabled: boolean
    video_clip_duration: number
  }
  onSave: (settings: {
    recognition_threshold?: number
    alert_cooldown_seconds?: number
    video_recording_enabled?: boolean
    video_clip_duration?: number
  }) => Promise<void>
}

export function RecognitionSettings({ settings, onSave }: RecognitionSettingsProps) {
  const [threshold, setThreshold] = useState(settings.recognition_threshold)
  const [cooldown, setCooldown] = useState(settings.alert_cooldown_seconds)
  const [videoEnabled, setVideoEnabled] = useState(settings.video_recording_enabled)
  const [videoDuration, setVideoDuration] = useState(settings.video_clip_duration)
  const [saving, setSaving] = useState(false)

  const hasChanges =
    threshold !== settings.recognition_threshold ||
    cooldown !== settings.alert_cooldown_seconds ||
    videoEnabled !== settings.video_recording_enabled ||
    videoDuration !== settings.video_clip_duration

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave({
        recognition_threshold: threshold,
        alert_cooldown_seconds: cooldown,
        video_recording_enabled: videoEnabled,
        video_clip_duration: videoDuration,
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recognition Settings</CardTitle>
        <CardDescription>
          Configure face recognition and alert parameters
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Recognition Threshold</Label>
              <span className="text-sm text-muted-foreground">
                {threshold.toFixed(2)}
              </span>
            </div>
            <Slider
              value={[threshold]}
              onValueChange={([value]) => setThreshold(value)}
              min={0.1}
              max={1.0}
              step={0.05}
            />
            <p className="text-xs text-muted-foreground">
              Minimum similarity score for face recognition match
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="cooldown">Alert Cooldown (seconds)</Label>
            <Input
              id="cooldown"
              type="number"
              value={cooldown}
              onChange={(e) => setCooldown(parseInt(e.target.value) || 0)}
              min={0}
              max={3600}
            />
            <p className="text-xs text-muted-foreground">
              Minimum time between alerts for the same person
            </p>
          </div>

          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label>Video Recording</Label>
              <p className="text-xs text-muted-foreground">
                Record video clips for alerts
              </p>
            </div>
            <Switch
              checked={videoEnabled}
              onCheckedChange={setVideoEnabled}
            />
          </div>

          {videoEnabled && (
            <div className="space-y-2">
              <Label htmlFor="videoDuration">Video Clip Duration (seconds)</Label>
              <Input
                id="videoDuration"
                type="number"
                value={videoDuration}
                onChange={(e) => setVideoDuration(parseInt(e.target.value) || 5)}
                min={3}
                max={30}
              />
              <p className="text-xs text-muted-foreground">
                Duration of video clips to record (3-30 seconds)
              </p>
            </div>
          )}
        </div>

        <Button onClick={handleSave} disabled={saving || !hasChanges}>
          {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Save Changes
        </Button>
      </CardContent>
    </Card>
  )
}
