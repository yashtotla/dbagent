/* ─────────────────────────────────────────────────────────────
   quiz.js — reusable retrieval-practice widget.
   Shared across all lessons in this workspace.

   Markup contract:

     <div class="quiz">
       <p class="quiz-q"><span class="num">Q1</span>Question text?</p>
       <ul class="quiz-opts">
         <li data-correct data-why="Shown when picked.">Right answer</li>
         <li data-why="Shown when picked.">Wrong answer</li>
       </ul>
     </div>

   Behaviour: one attempt per question, immediate feedback, the correct
   option is always revealed. Options are shuffled on load so the answer
   position carries no information across re-reads (spaced repetition —
   you will open these lessons again).

   A running score is appended to the last .quiz on the page.
   ───────────────────────────────────────────────────────────── */

(function () {
  "use strict";

  function shuffle(nodes) {
    for (var i = nodes.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      nodes[i].parentNode.insertBefore(nodes[i], nodes[j]);
    }
  }

  function init() {
    var quizzes = Array.prototype.slice.call(document.querySelectorAll(".quiz"));
    if (!quizzes.length) return;

    var answered = 0;
    var right = 0;

    var score = document.createElement("p");
    score.className = "quiz-score";
    score.textContent = "0 / " + quizzes.length + " answered";
    quizzes[quizzes.length - 1].appendChild(score);

    quizzes.forEach(function (quiz) {
      var list = quiz.querySelector(".quiz-opts");
      if (!list) return;

      var items = Array.prototype.slice.call(list.children);
      shuffle(items);

      var why = document.createElement("p");
      why.className = "quiz-why";
      why.hidden = true;
      quiz.appendChild(why);

      items.forEach(function (li) {
        var label = li.textContent.trim();
        var isCorrect = li.hasAttribute("data-correct");
        li.textContent = "";

        var btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = label;
        li.appendChild(btn);

        btn.addEventListener("click", function () {
          if (quiz.dataset.done) return;
          quiz.dataset.done = "1";

          items.forEach(function (other) {
            other.querySelector("button").disabled = true;
            if (other.hasAttribute("data-correct")) other.classList.add("is-correct");
          });
          if (!isCorrect) li.classList.add("is-wrong");

          why.textContent = (isCorrect ? "Correct. " : "Not quite. ") +
            (li.getAttribute("data-why") || "");
          why.className = "quiz-why " + (isCorrect ? "show-good" : "show-bad");
          why.hidden = false;

          answered++;
          if (isCorrect) right++;
          score.textContent = right + " / " + answered + " correct" +
            (answered === quizzes.length ? " — all answered" : "");
        });
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
