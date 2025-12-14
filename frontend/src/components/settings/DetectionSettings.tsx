import { useState } from "react"
import { Loader2 } from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"

interface DetectionSettingsProps {
  settings: {
    detection_confidence: number
    frame_skip: number
    enable_motion_trigger: boolean
  }
  onSave: (settings: {
    detection_confidence?: number
    frame_skip?: number
    enable_motion_trigger?: boolean
  }) => Promise<void>
}

export function DetectionSettings({ settings, onSave }: DetectionSettingsProps) {
  const [detectionConfidence, setDetectionConfidence] = useState(settings.detection_confidence)
  const [frameSkip, setFrameSkip] = useState(settings.frame_skip)
  const [motionTrigger, setMotionTrigger] = useState(settings.enable_motion_trigger)
  const [saving, setSaving] = useState(false)

  const hasChanges =
    detectionConfidence !== settings.detection_confidence ||
    frameSkip !== settings.frame_skip ||
    motionTrigger !== settings.enable_motion_trigger

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave({
        detection_confidence: detectionConfidence,
        frame_skip: frameSkip,
        enable_motion_trigger: motionTrigger,
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Detection Settings</CardTitle>
        <CardDescription>
          Configure face detection parameters
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Detection Confidence</Label>
              <span className="text-sm text-muted-foreground">
                {detectionConfidence.toFixed(2)}
              </span>
            </div>
            <Slider
              value={[detectionConfidence]}
              onValueChange={([value]) => setDetectionConfidence(value)}
              min={0.1}
              max={1.0}
              step={0.05}
            />
            <p className="text-xs text-muted-foreground">
              Minimum confidence score for face detection
            </p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Frame Skip</Label>
              <span className="text-sm text-muted-foreground">{frameSkip}</span>
            </div>
            <Slider
              value={[frameSkip]}
              onValueChange={([value]) => setFrameSkip(value)}
              min={0}
              max={10}
              step={1}
            />
            <p className="text-xs text-muted-foreground">
              Number of frames to skip between detections (higher = faster but less accurate)
            </p>
          </div>

          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label>Motion Trigger</Label>
              <p className="text-xs text-muted-foreground">
                Only detect faces when motion is detected
              </p>
            </div>
            <Switch
              checked={motionTrigger}
              onCheckedChange={setMotionTrigger}
            />
          </div>
        </div>

        <Button onClick={handleSave} disabled={saving || !hasChanges}>
          {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Save Changes
        </Button>
      </CardContent>
    </Card>
  )
}
