// Карусели фото: стрелки, точки и подсветка текущей точки при свайпе.
// Сама прокрутка — CSS scroll-snap, поэтому без этого скрипта фото тоже листаются.
(function () {
  function setup(carousel) {
    if (carousel.dataset.ready) return;
    carousel.dataset.ready = "true";
    const track = carousel.querySelector("[data-track]");
    const slides = Array.from(track.children);
    const dots = Array.from(carousel.querySelectorAll("[data-dot]"));
    // Позиции берём у самих слайдов: ширина бывает дробной, и деление на неё
    // иногда давало «застревание» на соседнем слайде.
    const current = () => {
      const distances = slides.map((slide) => Math.abs(slide.offsetLeft - track.scrollLeft));
      return distances.indexOf(Math.min(...distances));
    };
    const highlight = (index) => dots.forEach((dot, i) => dot.classList.toggle("is-active", i === index));
    const go = (index) => {
      const last = slides.length - 1;
      const target = index < 0 ? last : index > last ? 0 : index;
      // Переключение мгновенное: плавная прокрутка вместе со scroll-snap в части
      // браузеров срабатывает через раз. Свайп при этом остаётся плавным.
      track.scrollTo({ left: slides[target].offsetLeft, behavior: "auto" });
      highlight(target);
    };

    carousel.querySelector("[data-prev]")?.addEventListener("click", () => go(current() - 1));
    carousel.querySelector("[data-next]")?.addEventListener("click", () => go(current() + 1));
    dots.forEach((dot) => dot.addEventListener("click", () => go(Number(dot.dataset.dot))));
    track.addEventListener("keydown", (event) => {
      if (event.key === "ArrowLeft") go(current() - 1);
      if (event.key === "ArrowRight") go(current() + 1);
    });
    // При свайпе пальцем точку подсвечиваем по текущей позиции ленты.
    track.addEventListener("scroll", () => highlight(current()), { passive: true });
  }

  const init = (root) => root.querySelectorAll("[data-carousel]").forEach(setup);
  document.addEventListener("DOMContentLoaded", () => init(document));
  // HTMX подставляет новый блок товара при смене цвета — подключаем его карусель.
  document.addEventListener("htmx:load", (event) => init(event.target));
})();
