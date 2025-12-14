import { useState, useRef } from "react"
import { Camera, Upload, X, Loader2 } from "lucide-react"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import api from "@/services/api"

interface EnrollPersonDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

export function EnrollPersonDialog({
  open,
  onOpenChange,
  onSuccess,
}: EnrollPersonDialogProps) {
  const [name, setName] = useState("")
  const [idCard, setIdCard] = useState("")
  const [caseInfo, setCaseInfo] = useState("")
  const [watchlistStatus, setWatchlistStatus] = useState("")
  const [threatLevel, setThreatLevel] = useState("")
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [enrollMode, setEnrollMode] = useState<"upload" | "camera">("upload")

  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      setPreviewUrl(URL.createObjectURL(file))
    }
  }

  const handleCameraCapture = async () => {
    if (!name.trim()) {
      setError("Please enter a name first")
      return
    }

    setLoading(true)
    setError(null)

    try {
      await api.persons.enrollFromCamera(
        name.trim(),
        idCard || undefined,
        caseInfo || undefined,
        watchlistStatus || undefined,
        threatLevel || undefined
      )
      onSuccess()
      handleClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to capture from camera")
    } finally {
      setLoading(false)
    }
  }

  const handleUploadSubmit = async () => {
    if (!name.trim()) {
      setError("Please enter a name")
      return
    }

    if (!selectedFile) {
      setError("Please select an image")
      return
    }

    setLoading(true)
    setError(null)

    try {
      await api.persons.enroll(
        name.trim(),
        selectedFile,
        idCard || undefined,
        caseInfo || undefined,
        watchlistStatus || undefined,
        threatLevel || undefined
      )
      onSuccess()
      handleClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to enroll person")
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => {
    setName("")
    setIdCard("")
    setCaseInfo("")
    setWatchlistStatus("")
    setThreatLevel("")
    setSelectedFile(null)
    setPreviewUrl(null)
    setError(null)
    setEnrollMode("upload")
    onOpenChange(false)
  }

  const clearSelectedFile = () => {
    setSelectedFile(null)
    setPreviewUrl(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Enroll New Person</DialogTitle>
          <DialogDescription>
            Add a new person to the face recognition database.
          </DialogDescription>
        </DialogHeader>

        <Tabs value={enrollMode} onValueChange={(v) => setEnrollMode(v as "upload" | "camera")}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="upload">
              <Upload className="mr-2 h-4 w-4" />
              Upload Image
            </TabsTrigger>
            <TabsTrigger value="camera">
              <Camera className="mr-2 h-4 w-4" />
              Capture from Camera
            </TabsTrigger>
          </TabsList>

          <div className="mt-4 space-y-4">
            {/* Common Fields */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name *</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Enter full name"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="idCard">ID Card</Label>
                <Input
                  id="idCard"
                  value={idCard}
                  onChange={(e) => setIdCard(e.target.value)}
                  placeholder="Optional"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="caseInfo">Case Information</Label>
              <Input
                id="caseInfo"
                value={caseInfo}
                onChange={(e) => setCaseInfo(e.target.value)}
                placeholder="Optional case notes"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="watchlistStatus">Status</Label>
                <Select value={watchlistStatus} onValueChange={setWatchlistStatus}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="normal">Normal</SelectItem>
                    <SelectItem value="person of interest">Person of Interest</SelectItem>
                    <SelectItem value="watchlist">Watchlist</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="threatLevel">Threat Level</Label>
                <Select value={threatLevel} onValueChange={setThreatLevel}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select level" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Upload Tab Content */}
            <TabsContent value="upload" className="mt-0">
              <div className="space-y-2">
                <Label>Photo *</Label>
                {previewUrl ? (
                  <div className="relative">
                    <img
                      src={previewUrl}
                      alt="Preview"
                      className="h-48 w-full rounded-lg border object-cover"
                    />
                    <Button
                      variant="destructive"
                      size="icon"
                      className="absolute right-2 top-2"
                      onClick={clearSelectedFile}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ) : (
                  <div
                    className="flex h-48 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed hover:bg-muted/50"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Upload className="mb-2 h-8 w-8 text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">
                      Click to upload image
                    </p>
                    <p className="text-xs text-muted-foreground">
                      JPG, PNG up to 10MB
                    </p>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleFileChange}
                />
              </div>
            </TabsContent>

            {/* Camera Tab Content */}
            <TabsContent value="camera" className="mt-0">
              <div className="rounded-lg border bg-muted/50 p-4 text-center">
                <Camera className="mx-auto mb-2 h-8 w-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  The system will capture a face from the live camera stream.
                </p>
                <p className="mt-2 text-xs text-muted-foreground">
                  Make sure the person is clearly visible in the camera view.
                </p>
              </div>
            </TabsContent>

            {error && (
              <div className="rounded-lg border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
                {error}
              </div>
            )}
          </div>
        </Tabs>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          {enrollMode === "upload" ? (
            <Button onClick={handleUploadSubmit} disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Enroll Person
            </Button>
          ) : (
            <Button onClick={handleCameraCapture} disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Capture & Enroll
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
