// globally used username
let username = ''
// for staying in sync with the game this is global
let turn_count = 0
// keep an eye on next player to know if turns are allowed or not
let next_player = ''
// lock dragging of cards while waiting for trick being claimed
let cards_locked = false

$(document).ready(function () {
    const socket = io()

    let dragging = dragula([document.querySelector('#hand'),
        document.querySelector('#table'), {
            revertOnSpill: true,
            direction: 'horizontal'
        }
    ]);

    dragging.on('drop', function (card, target, source) {
        console.log('cards_locked:', cards_locked)
        if (source.id == 'hand' && target.id == 'table' && username == next_player && !cards_locked) {
            $('#table').append(card)
            socket.emit('played-card', {
                username: username,
                card_id: $(card).data('id'),
                card_name: $(card).data('name'),
                table: $(card).data('table')
            })
        } else if (source.id == 'hand' && target.id == 'hand') {
            return true
        } else if (source.id == 'table' || cards_locked || username != next_player) {
            dragging.cancel(true)
        }
    })

    socket.on('connect', function () {
        socket.emit('my event',
            {data: 'I\'m connected!'})

        socket.emit('who-am-i')
    })

    socket.on('you-are-what-you-is', function (msg) {
        if (username == '') {
            username = msg.username
        }
    })

    socket.on('new-table-available', function (msg) {
        $('#list_tables').html(msg.html)
    })

    socket.on('played-card-by-user', function (msg) {
        next_player = msg.next_player
        console.log(msg)
        // $('#hud_players').html('')
        // $('#hud_players').html(msg.html.hud_players)
        $('.hud_player').removeClass('border rounded p-2 text-black-50 bg-white')
        if (!msg.is_last_turn) {
            $('#hud_player_' + msg.next_player).addClass('border rounded p-2 text-black-50 bg-white')
        }
        if (username != msg.username) {
            $('#table').append(msg.html.card)
        }
        if (msg.is_last_turn) {
            cards_locked = true
            $('#turn_indicator').addClass('d-none')
            $('#claim_trick').removeClass('d-none')
        } else {
            cards_locked = false
            if (username == next_player) {
                $('#turn_indicator').removeClass('d-none')
            } else {
                $('#turn_indicator').addClass('d-none')
            }
            $('#claim_trick').addClass('d-none')
        }
        // anyway there is no need anymore to deal cards
        $('#deal_cards').addClass('d-none')
    })

    socket.on('grab-your-cards', function (msg) {
        socket.emit('my-cards-please', {
            username: username,
            table: msg.table
        })
    })

    socket.on('your-cards-please', function (msg) {
        next_player = msg.next_player
        cards_locked = false
        $('#table').html('')
        $('#hud_players').html(msg.html.hud_players)
        $('#hand').html(msg.html.cards_hand)
        $('#claim_trick').addClass('d-none')
        if (username == next_player) {
            $('#turn_indicator').removeClass('d-none')
        } else {
            $('#turn_indicator').addClass('d-none')
        }
    })

    socket.on('next-trick', function (msg) {
        next_player = msg.next_player
        console.log(msg)
        cards_locked = false
        $('#table').html('')
        if (username == next_player) {
            $('#turn_indicator').removeClass('d-none')
        } else {
            $('#turn_indicator').addClass('d-none')
        }

    })

    socket.on('round-finished', function (msg) {
        console.log('round-finished', msg)
        $('#claim_trick').addClass('d-none')
        // $('#next_round').removeClass('d-none')
        $('#modal_title').html('<strong>Runde beendet</strong>')
        // Inhalt des Dialogs erst einmal leeren, damit keine alten Reste darin kleben
        $('#modal_body').html(msg.html)
        $("#modal_dialog").modal()
    })

    socket.on('start-next-round', function (msg) {
        if (username == msg.dealer) {
            $('#deal_cards').removeClass('d-none')
        } else {
            $('#deal_cards').addClass('d-none')
        }
        $('#next_round').addClass('d-none')
        $('#claim_trick').addClass('d-none')

    })


    $(document).on('click', '#new_table', function () {
        socket.emit('new-table', {button: 'new_table'})
    })

    $(document).on('click', '.list-item-table', function () {
        socket.emit('enter-table', {
            username: username,
            table: $(this).data('table')
        })
    })

    $(document).on('click', '#deal_cards', function () {
        socket.emit('deal-cards', {
            username: username,
            table: $(this).data('table')
        })
    })

    $(document).on('click', '#claim_trick', function () {
        console.log('claim trick')
        socket.emit('claim-trick', {
            username: username,
            table: $(this).data('table')
        })
    })

    $(document).on('click', '#next_round', function () {
        console.log('next_round')
        $('#next_round').addClass('d-none')
        socket.emit('ready-for-next-round', {
            username: username,
            table: $(this).data('table')
        })
    })

})