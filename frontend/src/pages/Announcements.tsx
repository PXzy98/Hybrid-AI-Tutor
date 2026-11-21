import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Megaphone, Pencil, Pin, PinOff, Plus, Trash2 } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { api, type Announcement, type Course } from "@/api/endpoints";
import { CharCount, EmptyState, ErrorNote, Loading, PageHeader, REQUIRED_LABEL, SaveHint, StatusText } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/i18n";
import { useFormat } from "@/lib/format";

/** How many announcements the student's course home shows; the rest are on the Announcements page. */
export const HOME_COUNT = 3;

const useAnnouncements = (course: Course) =>
  useQuery({ queryKey: ["announcements", course.id], queryFn: () => api.announcements(course.id) });

/** One announcement: title, date, pinned mark and the plain text body (line breaks kept, nothing rendered as
 *  Markdown or HTML). `actions` are the instructor's buttons; `compact` clamps the body to two lines (the full
 *  text stays in the page for screen readers and is on the Announcements page). */
function AnnouncementCard({ item, actions, level = 3, compact = false }: { item: Announcement; actions?: ReactNode; level?: 3 | 4; compact?: boolean }) {
  const { t } = useI18n();
  const fmt = useFormat();
  const Heading = level === 3 ? "h3" : "h4";
  const edited = item.updated_at !== item.created_at;
  return (
    <article className={`rounded-xl border bg-card ${compact ? "space-y-1 px-3 py-2" : "space-y-2 p-4"}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 space-y-1">
          <Heading className="flex flex-wrap items-center gap-2 text-sm font-semibold break-words">
            {item.title}
            {item.pinned && <Badge variant="info"><Pin aria-hidden />{t("ann.pinned")}</Badge>}
          </Heading>
          <p className="text-xs text-muted-foreground">
            <time dateTime={item.created_at}>{fmt.date(item.created_at)}</time>
            {edited && ` · ${t("ann.edited", { date: fmt.date(item.updated_at) })}`}
          </p>
        </div>
        {actions && <div className="flex flex-wrap gap-1">{actions}</div>}
      </div>
      {item.body && <p className={`text-sm whitespace-pre-wrap break-words ${compact ? "line-clamp-2" : ""}`}>{item.body}</p>}
    </article>
  );
}

// ------------------------------------------------------------------------------------------------ student
/** The latest announcements on the student's course home (the chat of a new conversation): pinned first. */
export function LatestAnnouncements({ course }: { course: Course }) {
  const { t } = useI18n();
  const list = useAnnouncements(course);
  if (!list.data) return null;  // loading, or failed: the chat stays usable without them
  const shown = list.data.slice(0, HOME_COUNT);
  return (
    <section aria-labelledby="home-announcements" className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id="home-announcements" className="flex items-center gap-2 text-sm font-semibold">
          <Megaphone aria-hidden className="size-4 text-muted-foreground" />{t("ann.title")}
        </h3>
        {shown.length > 0 && (
          <Link to={`/courses/${course.id}/announcements`} className="text-sm font-medium underline underline-offset-2">
            {list.data.length > HOME_COUNT ? t("ann.seeAll", { n: list.data.length }) : t("ann.readMore")}
          </Link>
        )}
      </div>
      {shown.length === 0
        ? <p className="text-sm text-muted-foreground">{t("ann.noneStudent")}</p>
        : <ul className="space-y-2">{shown.map((a) => <li key={a.id}><AnnouncementCard item={a} level={4} compact /></li>)}</ul>}
    </section>
  );
}

/** Every announcement of the course, for students. */
export function StudentAnnouncements({ course }: { course: Course }) {
  const { t } = useI18n();
  const list = useAnnouncements(course);
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title={t("ann.title")} description={t("ann.studentIntro")} />
      <ErrorNote error={list.error} />
      {list.isLoading && <Loading variant="list" />}
      {list.data?.length === 0 && <EmptyState icon={Megaphone} title={t("ann.emptyTitle")}>{t("ann.noneStudent")}</EmptyState>}
      {!!list.data?.length && <ul className="space-y-3">{list.data.map((a) => <li key={a.id}><AnnouncementCard item={a} /></li>)}</ul>}
    </div>
  );
}

// --------------------------------------------------------------------------------------------- instructor
/** The instructor's announcements: write, edit and pin them, delete after a confirmation. */
export default function InstructorAnnouncements({ course }: { course: Course }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const list = useAnnouncements(course);
  const [saved, setSaved] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<Announcement | null>(null);
  const newButton = useRef<HTMLButtonElement>(null);
  const deleted = useRef(false);
  const refocus = useRef<number | null>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ["announcements", course.id] });
  const pin = useMutation({
    mutationFn: (a: Announcement) => api.updateAnnouncement(course.id, a.id, { pinned: !a.pinned }),
    onSuccess: async (_, a) => { refocus.current = a.id; await refresh(); setSaved(true); },
  });
  // the pinned item moves in the list: its pin button keeps the focus (the old node is gone)
  useEffect(() => {
    if (refocus.current === null || pin.isPending) return;
    document.getElementById(`ann-pin-${refocus.current}`)?.focus();
    refocus.current = null;
  }, [list.data, pin.isPending]);
  const remove = useMutation({
    mutationFn: (a: Announcement) => api.deleteAnnouncement(course.id, a.id),
    onSuccess: async () => { deleted.current = true; setPendingDelete(null); await refresh(); },
  });
  const done = () => { setSaved(true); };
  return (
    <div className="space-y-6">
      <PageHeader title={t("ann.title")} description={t("ann.intro")}
                  actions={<AnnouncementDialog course={course} onSaved={done} trigger={
                    <Button ref={newButton} type="button" onClick={() => setSaved(false)}><Plus aria-hidden />{t("ann.new")}</Button>} />} />
      <ErrorNote error={list.error} />
      {saved && <StatusText>{t("settings.saved")}</StatusText>}
      <ErrorNote error={pin.error} />
      {list.isLoading && <Loading variant="list" />}
      {list.data?.length === 0 && <EmptyState icon={Megaphone} title={t("ann.emptyTitle")}>{t("ann.none")}</EmptyState>}
      {!!list.data?.length && (
        <ul className="space-y-3">
          {list.data.map((a) => (
            <li key={a.id}>
              <AnnouncementCard item={a} actions={<>
                <Button type="button" size="sm" variant="ghost" id={`ann-pin-${a.id}`} aria-pressed={a.pinned} loading={pin.isPending && pin.variables?.id === a.id}
                        aria-label={t(a.pinned ? "ann.unpinFor" : "ann.pinFor", { name: a.title })}
                        onClick={() => { setSaved(false); pin.mutate(a); }}>
                  {a.pinned ? <PinOff aria-hidden /> : <Pin aria-hidden />}{t(a.pinned ? "ann.unpin" : "ann.pin")}
                </Button>
                <AnnouncementDialog course={course} item={a} onSaved={done} trigger={
                  <Button type="button" size="sm" variant="outline" aria-label={t("content.editFor", { name: a.title })}
                          onClick={() => setSaved(false)}><Pencil aria-hidden />{t("models.edit")}</Button>} />
                <Button type="button" size="icon-sm" variant="ghost" className="text-muted-foreground hover:text-destructive"
                        aria-label={t("ann.deleteFor", { name: a.title })} onClick={() => { setSaved(false); remove.reset(); setPendingDelete(a); }}>
                  <Trash2 aria-hidden />
                </Button>
              </>} />
            </li>
          ))}
        </ul>
      )}
      <Dialog open={!!pendingDelete} onOpenChange={(o) => { if (!o) setPendingDelete(null); }}>
        {/* the deleted row's button is gone: focus goes to "New announcement" instead */}
        <DialogContent onCloseAutoFocus={(e) => {
          if (!deleted.current) return;
          deleted.current = false;
          e.preventDefault();
          newButton.current?.focus();
        }}>
          <DialogHeader>
            <DialogTitle>{t("ann.deleteTitle")}</DialogTitle>
            <DialogDescription>{t("ann.deleteBody", { name: pendingDelete?.title ?? "" })}</DialogDescription>
          </DialogHeader>
          <ErrorNote error={remove.error} />
          <DialogFooter>
            <DialogClose asChild><Button type="button" variant="outline">{t("end.cancel")}</Button></DialogClose>
            <Button type="button" variant="destructive" loading={remove.isPending}
                    onClick={() => pendingDelete && remove.mutate(pendingDelete)}>{t("ann.delete")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** Write a new announcement, or edit `item`. The server refuses student data (privacy scan) and a blank title. */
function AnnouncementDialog({ course, item, trigger, onSaved }: { course: Course; item?: Announcement; trigger: ReactNode; onSaved: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const initial = { title: item?.title ?? "", body: item?.body ?? "", pinned: item?.pinned ?? false };
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(initial);
  const save = useMutation({
    mutationFn: () => item ? api.updateAnnouncement(course.id, item.id, form) : api.createAnnouncement(course.id, form),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["announcements", course.id] });
      setOpen(false);
      onSaved();
    },
  });
  const p = item ? `ann-${item.id}` : "ann-new";
  function submit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }
  return (
    <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (next) { setForm(initial); save.reset(); } }}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{t(item ? "ann.editTitle" : "ann.newTitle")}</DialogTitle>
            <DialogDescription>{t("ann.formHint")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5"><Label htmlFor={`${p}-title`} className={REQUIRED_LABEL}>{t("ann.fieldTitle")}</Label>
            <Input id={`${p}-title`} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required aria-required maxLength={200} />
            <CharCount value={form.title} max={200} /></div>
          <div className="grid gap-1.5"><Label htmlFor={`${p}-body`}>{t("ann.fieldBody")}</Label>
            <Textarea id={`${p}-body`} value={form.body} rows={6} onChange={(e) => setForm({ ...form, body: e.target.value })} maxLength={4000} />
            <CharCount value={form.body} max={4000} /></div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="accent-primary" checked={form.pinned} onChange={(e) => setForm({ ...form, pinned: e.target.checked })} />
            {t("ann.fieldPinned")}
          </label>
          <ErrorNote error={save.error} />
          <DialogFooter className="items-center">
            {!form.title.trim() && <SaveHint id={`${p}-hint`}>{t("ann.fillTitle")}</SaveHint>}
            <Button loading={save.isPending} type="submit" aria-describedby={form.title.trim() ? undefined : `${p}-hint`} disabled={save.isPending || !form.title.trim()}>{save.isPending ? t("settings.saving") : t("settings.save")}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
