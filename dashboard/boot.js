'use strict';
(function(app){
  if (!app || app.started) return;
  app.started = true;
  app.start();
})(globalThis.WikiStudioApp);
