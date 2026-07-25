/** A(z) /utokovetes/[id] részletnézet keret nélküli változata, felugró ablakhoz
 * (lásd components/RecordDetailModal.tsx). Szándékosan UGYANAZT a
 * komponenst exportálja újra, mint a rendes oldal - így a két nézet nem tud
 * elcsúszni egymástól. Az alkalmazás-keretet (oldalsáv, felső sáv,
 * vissza-link) az /embed layout rejti el. */
export { default } from "@/app/(app)/utokovetes/[id]/page";
