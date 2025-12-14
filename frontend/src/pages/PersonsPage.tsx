import { useState, useEffect, useCallback } from "react"
import { Search, UserPlus, RefreshCw } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  PersonsTable,
  EnrollPersonDialog,
  PersonDetailsDialog,
} from "@/components/persons"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import api from "@/services/api"

interface Person {
  id: number
  name: string
  id_card?: string
  watchlist_status?: string
  threat_level?: string
  detection_count?: number
  last_detection?: string
}

export function PersonsPage() {
  const [persons, setPersons] = useState<Person[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState("")
  const [enrollDialogOpen, setEnrollDialogOpen] = useState(false)
  const [detailsDialogOpen, setDetailsDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedPerson, setSelectedPerson] = useState<Person | null>(null)
  const [deleting, setDeleting] = useState(false)

  const fetchPersons = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.persons.list(searchQuery || undefined)
      setPersons(data || [])
    } catch {
      console.error("Failed to fetch persons")
    } finally {
      setLoading(false)
    }
  }, [searchQuery])

  // Debounce search
  useEffect(() => {
    const timeout = setTimeout(() => {
      fetchPersons()
    }, 300)
    return () => clearTimeout(timeout)
  }, [fetchPersons])

  const handleViewDetails = (person: Person) => {
    setSelectedPerson(person)
    setDetailsDialogOpen(true)
  }

  const handleAddImage = (person: Person) => {
    // For now, just open details - we could add a separate dialog for this
    setSelectedPerson(person)
    setDetailsDialogOpen(true)
  }

  const handleDeleteClick = (person: Person) => {
    setSelectedPerson(person)
    setDeleteDialogOpen(true)
  }

  const handleDelete = async () => {
    if (!selectedPerson) return

    setDeleting(true)
    try {
      await api.persons.delete(selectedPerson.id)
      setDeleteDialogOpen(false)
      setSelectedPerson(null)
      fetchPersons()
    } catch {
      console.error("Failed to delete person")
    } finally {
      setDeleting(false)
    }
  }

  const handleEnrollSuccess = () => {
    fetchPersons()
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Persons</h1>
          <p className="text-muted-foreground">
            Manage enrolled persons in the face recognition database
          </p>
        </div>
        <Button onClick={() => setEnrollDialogOpen(true)}>
          <UserPlus className="mr-2 h-4 w-4" />
          Enroll Person
        </Button>
      </div>

      {/* Search and Filters */}
      <div className="flex gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by name or ID card..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Button variant="outline" onClick={fetchPersons} disabled={loading}>
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>

      {/* Table */}
      <PersonsTable
        persons={persons}
        onViewDetails={handleViewDetails}
        onAddImage={handleAddImage}
        onDelete={handleDeleteClick}
      />

      {/* Summary */}
      <div className="text-sm text-muted-foreground">
        Total: {persons.length} persons enrolled
      </div>

      {/* Enroll Dialog */}
      <EnrollPersonDialog
        open={enrollDialogOpen}
        onOpenChange={setEnrollDialogOpen}
        onSuccess={handleEnrollSuccess}
      />

      {/* Details Dialog */}
      <PersonDetailsDialog
        person={selectedPerson}
        open={detailsDialogOpen}
        onOpenChange={setDetailsDialogOpen}
      />

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Person</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{selectedPerson?.name}"? This
              action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
