import { Users, Bell, Video, Cpu } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"

interface StatsOverviewProps {
  personCount: number
  alertCount: number
  fps: number
  gpuUsage: number
}

export function StatsOverview({ personCount, alertCount, fps, gpuUsage }: StatsOverviewProps) {
  const stats = [
    {
      name: "Enrolled Persons",
      value: personCount,
      icon: Users,
      color: "text-blue-500",
      bgColor: "bg-blue-500/10",
    },
    {
      name: "Active Alerts",
      value: alertCount,
      icon: Bell,
      color: "text-red-500",
      bgColor: "bg-red-500/10",
    },
    {
      name: "Stream FPS",
      value: fps.toFixed(2),
      icon: Video,
      color: "text-green-500",
      bgColor: "bg-green-500/10",
      suffix: " fps",
    },
    {
      name: "GPU Usage",
      value: gpuUsage,
      icon: Cpu,
      color: "text-purple-500",
      bgColor: "bg-purple-500/10",
      suffix: "%",
    },
  ]

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat) => {
        const Icon = stat.icon
        return (
          <Card key={stat.name}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    {stat.name}
                  </p>
                  <p className="text-2xl font-bold">
                    {stat.value}
                    {stat.suffix}
                  </p>
                </div>
                <div className={`rounded-full p-3 ${stat.bgColor}`}>
                  <Icon className={`h-5 w-5 ${stat.color}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
