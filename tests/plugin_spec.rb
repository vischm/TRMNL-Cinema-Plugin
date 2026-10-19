# frozen_string_literal: true

require 'zlib'

# Rendering tests, run with `bin/trmnlp test` (add `--report report` for a page of every screen it drew).
# Docs: https://github.com/usetrmnl/trmnlp/blob/main/docs/testing.md
RSpec.describe 'Cinema' do
  let(:programme) { Zlib::GzipReader.open(File.join(__dir__, 'fixtures', 'cinema_leipzig.html.gz'), &:read) }

  # Mocks only answer the transform's requests; the page loads images itself, so the poster is inlined
  let(:poster_url) { "data:image/png;base64,#{[File.binread(File.join(__dir__, 'fixtures', 'poster.png'))].pack('m0')}" }

  let(:film) do
    { name: 'Film', releaseYear: 2026, rating: 3.94, links: [{ type: 'tmdb', id: '1' }],
      poster: { sizes: [{ width: 300, height: 450, url: poster_url }] } }
  end

  let(:watched) do
    <<~XML
      <?xml version="1.0" encoding="utf-8"?>
      <rss xmlns:letterboxd="https://letterboxd.com" xmlns:tmdb="https://themoviedb.org"><channel>
        <item><letterboxd:watchedDate>2026-10-01</letterboxd:watchedDate><tmdb:movieId>2</tmdb:movieId></item>
        <item><letterboxd:watchedDate>2026-10-02</letterboxd:watchedDate><tmdb:tvId>3</tmdb:tvId></item>
      </channel></rss>
    XML
  end

  # Canned answers for cinema.de and Letterboxd. Header names must be lowercase to replace trmnlp's
  # default content-type instead of adding a second one.
  let(:mocks) do
    {
      'https://www.cinema.de/kino/kinoprogramm/*' => { body: programme, headers: { 'content-type' => 'text/html; charset=utf-8' } },
      'https://api.letterboxd.com/api/v0/search*' => { json: { items: [{ score: 1, film: }] } },
      'https://letterboxd.com/*/rss/' => { body: watched, headers: { 'content-type' => 'application/rss+xml' } }
    }
  end

  let(:custom_fields) { { city: 'Leipzig', letterboxd_username: 'someone' } }

  # 10:00 in Leipzig on the day the saved programme is from
  let(:now) { '2026-10-19T08:00:00Z' }

  # Every view on TRMNL's devices, a failing API and every select option, checked for page errors and leaked values.
  it_behaves_like 'a publishable recipe'

  it 'shows the three best films of the day' do
    screen = trmnl.render(view: 'full', device: 'og_plus', mocks:, custom_fields:, now:)
    expect(screen.result.data['movies'].size).to eq(3)
    expect(screen).to have_text('Now in Theaters').and have_text('Leipzig').and have_text('3.9')
  end

  it 'explains an unknown city' do
    screen = trmnl.render(view: 'full', device: 'og_plus', now:, custom_fields: { city: 'Gibtsnicht' },
                          mocks: { 'https://www.cinema.de/*' => { status: 404, body: 'not found' } })
    expect(screen).to have_text("cinema.de has no cinemas for 'gibtsnicht'")
  end
end
