
(function() {
    "use strict";

    var Bungee = window.Bungee = {
        beginChars: [9686, 57690, 57701, 57705, 57709, 57717, 57725, 57733, 57713],
        endChars: [9687, 10145, 57702, 57706, 57710, 57718, 57726, 57734, 57714],
        shapeChars: [11035, 11044, 57693, 57694, 57695, 57696, 57729, 57730, 57731, 57732],
        
        shapeInputList: function(list) {
            var i, u, c;
            var l = window.Bungee[list + 'Chars'];
            if (!l) {
                return;
            }
            document.write('<ul><li>');
            document.write('<input id="' + list + '-" type="radio" name="' + list + '" value="" checked>');
            document.write('<label for="' + list + '-">&nbsp;&nbsp;</label>');
            document.write('</li>');
            for (i in l) {
                u = l[i];
                c = String.fromCharCode(u);
                document.write('<li>');
                document.write('<input id="' + list + '-' + u + '" type="radio" name="' + list + '" value="' + u + '">');
                document.write('<label for="' + list + '-' + u + '">' + c + '</label>');
                document.write('</li>');
            }
            document.write('</ul>');
        },
        
        makeLayers: function(el) {
            if (typeof el === 'number') {
                el = this;
            }
            var master = $(el);
            if (master.hasClass('already-done')) {
                return;
            }
            //remember the content and then get rid of it
            var text = master.html().trim();
            master.html('<div></div>');
            var wrapper = master.children();
            wrapper.append("<div class='shadow'><span>" + text + "</span></div>");
            wrapper.append("<div class='outline'><span>" + text + "</span></div>");
            wrapper.append("<div class='regular'><span>" + text + "</span></div>");
            wrapper.append("<div class='inline'><span>" + text + "</span></div>");

            master.addClass('already-done', true);

            if (!/shadow|outline|regular|inline/.test(el.className)) {
                master.addClass('shadow outline regular inline');
            }
        },
        
        cleanupText: function(text) {
            return text.replace(/\s+/g, ' ').trim();
        }
    };

    //pretty up Bungee elements on document ready
    $(function() {
        // see if browser support writing-mode
        var test = $('<div class="bungee vertical" style="display:none"></div>');
        $('body').append(test);
        console.log(test.css('writing-mode'));
        if (!test.css('writing-mode')) {
            $('html').addClass('no-vertical-text');
        }
        $('.bungee').each(Bungee.makeLayers);
    });
})();
